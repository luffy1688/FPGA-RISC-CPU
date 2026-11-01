/* host_command_eval = offline evaluation adapter, never linked into FPGA firmware.
 * model mode records raw class AND guarded decode. forced mode isolates the
 * decimal argument contract from classification; it does not simulate hardware.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "byte_tool_model.h"

int main(int argc, char **argv) {
    nr_prediction_t prediction = {0};
    nr_tool_request_t request = {0};
    const char *text;
    int valid = 0;
    int model_rc = 0;
    unsigned i;
    if (argc == 3 && !strcmp(argv[1], "model")) {
        text = argv[2];
        if (strlen(text) > 0 && strlen(text) <= 64) {
            model_rc = nr_model_predict((const uint8_t *)text,
                                       (uint32_t)strlen(text), &prediction);
            valid = model_rc == 0;
        }
    } else if (argc == 4 && !strcmp(argv[1], "forced")) {
        long index = strtol(argv[2], 0, 10);
        if (index < 0 || index >= 6) return 2;
        text = argv[3];
        prediction.tool = (nr_tool_t)index;
        prediction.margin = 10000;
        valid = 1;
    } else {
        fprintf(stderr, "usage: command_eval model TEXT | forced TOOL_INDEX TEXT\n");
        return 2;
    }
    if (model_rc) {
        request.tool = NR_REJECT;
        request.status = NR_TOOL_BACKEND_ERROR;
    } else {
        nr_tool_decode_prediction((const uint8_t *)text, (uint32_t)strlen(text),
                                  valid ? &prediction : 0, &request);
    }
    printf("{\"prediction_valid\":%s,\"model_rc\":%d,\"raw_index\":%d,",
           valid ? "true" : "false", model_rc, valid ? (int)prediction.tool : -1);
    printf("\"final_index\":%d,\"status\":%d,\"argument\":%d,\"margin\":%d,\"logits\":[",
           (int)request.tool, (int)request.status, request.argument, request.margin);
    for (i = 0; i < 6; i++) printf("%s%d", i ? "," : "", prediction.logits[i]);
    printf("],\"operation\":%u,\"selection_source\":%u}\n",
           (unsigned)request.operation,(unsigned)request.selection_source);
    return 0;
}
