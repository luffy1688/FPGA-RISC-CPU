/* host_acceptance = 主机侧窄验收：只检查本次后端中止传播和参数解码。
   fake backend 不计算硬件结果；返回1要求模型安全回退到相同的整数软件实现。 */
#include "byte_tool_model.h"
#include <stdio.h>
#include <string.h>

static unsigned gemv_calls;
static unsigned fatal_at;
static unsigned checks;
static unsigned failures;

static int fake_backend(const uint8_t *weight, const int8_t *input,
                        int32_t *raw, uint32_t rows, uint32_t cols,
                        uint32_t flags) {
    (void)weight; (void)input; (void)raw;
    (void)rows; (void)cols; (void)flags;
    gemv_calls++;
    return gemv_calls == fatal_at ? NR_GEMV_FATAL : 1;
}

static void check(int condition, const char *name) {
    checks++;
    if (!condition) {
        fprintf(stderr, "FAIL HOST_MODEL: %s\n", name);
        failures++;
    }
}

/* 显式传入已有prediction；参数语法测试不应再次调用神经网络。 */
static void check_decode(nr_tool_t tool, const char *text,
                         nr_tool_status_t expected, int32_t argument) {
    nr_prediction_t prediction = {0};
    nr_tool_request_t request;
    unsigned before = gemv_calls;
    prediction.tool = tool;
    prediction.margin = 19;
    nr_tool_status_t status = nr_tool_decode_prediction(
        (const uint8_t *)text, (uint32_t)strlen(text), &prediction, &request);
    checks++;
    if (status != expected || request.status != expected ||
        request.tool != tool || request.margin != prediction.margin ||
        request.argument != (expected == NR_TOOL_OK ? argument : 0) ||
        gemv_calls != before) {
        fprintf(stderr, "FAIL HOST_MODEL: decode '%s', status=%d, argument=%ld\n",
                text, (int)status, (long)request.argument);
        failures++;
    }
}

static void check_fatal_predict(unsigned position, const char *name) {
    const uint8_t input[] = {'x'};
    nr_prediction_t prediction, initial;
    memset(&prediction, 0x5a, sizeof(prediction));
    initial = prediction;
    gemv_calls = 0;
    fatal_at = position;
    int status = nr_model_predict(input, 1, &prediction);
    check(status == NR_GEMV_FATAL, name);
    check(gemv_calls == position, "fatal stops further GEMV jobs");
    check(memcmp(&prediction, &initial, sizeof(prediction)) == 0,
          "fatal does not publish a partial prediction");
}

static void check_fatal_decode(unsigned position) {
    const uint8_t input[] = {'x'};
    nr_tool_request_t request;
    memset(&request, 0x5a, sizeof(request));
    gemv_calls = 0;
    fatal_at = position;
    nr_tool_status_t status = nr_tool_decode(input, 1, &request);
    check(status == NR_TOOL_BACKEND_ERROR, "decode reports backend error");
    check(request.status == NR_TOOL_BACKEND_ERROR, "stored status is backend error");
    check(request.tool == NR_REJECT && request.argument == 0 && request.margin == 0,
          "backend error cannot produce an actionable request");
    check(gemv_calls == position, "decode stops at fatal GEMV");
}

int main(void) {
    const uint8_t input[] = {'x'};
    nr_prediction_t reference = {0}, fallback = {0};
    nr_model_set_gemv_backend(0);
    check(nr_model_predict(input, 1, &reference) == 0,
          "one-byte software inference completes");
    nr_model_set_gemv_backend(fake_backend);
    gemv_calls = 0;
    fatal_at = 0;
    check(nr_model_predict(input, 1, &fallback) == 0,
          "nonfatal backend failure falls back to software");
    check(gemv_calls == 13, "one-byte two-layer model has thirteen GEMV jobs");
    check(memcmp(&fallback, &reference, sizeof(reference)) == 0,
          "fallback logits and selected tool equal software");

    check_fatal_predict(1, "first GEMV fatal propagates");
    check_fatal_predict(13, "last classification-head fatal propagates");
    check_fatal_decode(1);
    check_fatal_decode(13);

    check_decode(NR_SET_LED, "set led", NR_TOOL_MISSING_ARGUMENT, 0);
    check_decode(NR_SET_LED, "set led 1 2", NR_TOOL_BAD_ARGUMENT, 0);
    check_decode(NR_SET_LED, "set led 12.5", NR_TOOL_BAD_ARGUMENT, 0);
    check_decode(NR_SET_LED, "set led -1", NR_TOOL_OUT_OF_RANGE, 0);
    check_decode(NR_SET_LED, "set led 0", NR_TOOL_OK, 0);
    check_decode(NR_SET_LED, "set led 255", NR_TOOL_OK, 255);
    check_decode(NR_SET_LED, "set led 256", NR_TOOL_OUT_OF_RANGE, 0);
    check_decode(NR_SET_PWM, "set pwm", NR_TOOL_MISSING_ARGUMENT, 0);
    check_decode(NR_SET_PWM, "set pwm 1 2", NR_TOOL_BAD_ARGUMENT, 0);
    check_decode(NR_SET_PWM, "set pwm 1.5", NR_TOOL_BAD_ARGUMENT, 0);
    check_decode(NR_SET_PWM, "set pwm -1", NR_TOOL_OUT_OF_RANGE, 0);
    check_decode(NR_SET_PWM, "set pwm 0", NR_TOOL_OK, 0);
    check_decode(NR_SET_PWM, "set pwm 100", NR_TOOL_OK, 100);
    check_decode(NR_SET_PWM, "set pwm 101", NR_TOOL_OUT_OF_RANGE, 0);
    check_decode(NR_REJECT, "set led 10", NR_TOOL_REJECTED, 0);
    {
        nr_prediction_t low = {0};
        nr_tool_request_t request;
        low.tool = NR_SET_LED;
        low.margin = NR_MIN_CONFIDENCE_MARGIN - 1;
        nr_tool_status_t status = nr_tool_decode_prediction(
            (const uint8_t *)"set led 7", 9, &low, &request);
        check(status == NR_TOOL_REJECTED && request.tool == NR_REJECT &&
              request.status == NR_TOOL_REJECTED,
              "low-confidence prediction is rejected before GPIO");
    }

    {
        static const struct {const char *text;nr_tool_t tool;} denied[]={
            {"不要设置LED为7",NR_SET_LED},{"do not change LED to 10",NR_SET_LED},
            {"不要读取温度",NR_READ_TEMP},{"led 7 pwm 25",NR_SET_LED},
            {"translate 7",NR_SET_LED},{"pwm 25",NR_SET_LED}
        };
        unsigned i;
        for(i=0;i<sizeof(denied)/sizeof(denied[0]);i++) {
            nr_prediction_t prediction={0};nr_tool_request_t request;
            prediction.tool=denied[i].tool;prediction.margin=999;
            nr_tool_status_t status=nr_tool_decode_prediction(
                (const uint8_t *)denied[i].text,(uint32_t)strlen(denied[i].text),&prediction,&request);
            check(status==NR_TOOL_POLICY_REJECTED && request.tool==NR_REJECT &&
                  request.argument==0,"policy rejects negation/conflict/domain mismatch before dispatch");
        }
    }
    nr_model_set_gemv_backend(0);
    if (failures) return 1;
    printf("PASS HOST_MODEL: %u checks, software fallback, first/head fatal propagation, no actionable backend-error request, explicit argument boundaries\n", checks);
    return 0;
}
