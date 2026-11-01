/* main = 裸机入口；SELFTEST比较实现，正常镜像通过UART接收用户指令。 */
#include "byte_tool_model.h"
#include "byte_tool_xnd.h"
#include "tool_dispatch.h"
#include "link_protocol.h"
#include "../platform/needle_platform.h"
#include "../platform/needle_pmu.h"
/* 7种配置共用同一RTL和权重；:config命令只在NR_READY之后改变运行策略。 */
static const struct {uint32_t mode,graph,dot4;} configs[]={
    {0,0,0},{1,0,0},{2,0,0},{1,1,0},{2,1,0},{3,1,0},{3,1,1}
};
#ifndef NR_MODEL_SELFTEST
static void select_config(uint32_t id) {
    nr_model_xnd_set_mode((nr_xnd_mode_t)configs[id].mode);
    nr_model_set_qkv_interleaved(configs[id].graph);
    nr_model_set_attention_dot4(configs[id].dot4);
    nr_puts("NR_CONFIG {\"config\":");nr_put_u32(id);
    nr_puts(",\"mode\":");nr_put_u32(configs[id].mode);
    nr_puts(",\"graph\":");nr_put_u32(configs[id].graph);
    nr_puts(",\"dot4\":");nr_put_u32(configs[id].dot4);nr_puts("}\n");
}
static uint32_t fast_enabled=1,compact_enabled=1;
static int line_is(const uint8_t *line,uint32_t n,const char *text) {
    uint32_t i=0;while(text[i]){if(i>=n||line[i]!=(uint8_t)text[i])return 0;i++;}return i==n;
}
static void report_fast_mode(void) {
    nr_puts("NR_FAST_MODE {\"enabled\":");nr_put_u32(fast_enabled);nr_puts("}\n");
}
static void report_format(void) {
    nr_puts("NR_FORMAT {\"compact\":");nr_put_u32(compact_enabled);nr_puts("}\n");
}
/* Debug controls never pass through the language model. :io is read-only. */
static int control_config(const uint8_t *line,uint32_t length,uint32_t *id) {
    static const char prefix[]=":config ";uint32_t i;
    if(!length || line[0]!=':')return 0;
    if(line_is(line,length,":fast 0")||line_is(line,length,":fast 1")) {
        fast_enabled=line[6]-'0';report_fast_mode();return 1;
    }
    if(line_is(line,length,":format full")||line_is(line,length,":format compact")) {
        compact_enabled=length==15;report_format();return 1;
    }
    if(line_is(line,length,":worker start")) {
        if(*(volatile uint32_t*)0x40020008u&1u){nr_puts("NR_WORKER {\"phase\":\"busy\"}\n");return 1;}
        *(volatile uint32_t*)0x40020000u=1;
        nr_puts("NR_WORKER {\"phase\":\"started\",\"isolated_ram_bytes\":65536}\n");return 1;
    }
    if(line_is(line,length,":worker status")) {
        nr_puts("NR_WORKER {\"status\":");nr_put_u32(*(volatile uint32_t*)0x40020008u);
        nr_puts(",\"cycles\":");nr_put_u32(*(volatile uint32_t*)0x4002000cu);nr_puts("}\n");return 1;
    }
    if(line_is(line,length,":io")) {
        uint32_t led=NR_LED,period=NR_MMIO(0x10000038u),high=NR_MMIO(0x10000034u),enabled=NR_MMIO(0x1000003cu)&1u;
        uint32_t valid=period==NR_PWM_PERIOD_TICKS && high<=period;
        uint32_t duty=valid?(high*100u)/period:0;
        nr_puts("NR_IO {\"led_mask\":");nr_put_u32(led);
        nr_puts(",\"pwm_period\":");nr_put_u32(period);nr_puts(",\"pwm_high\":");nr_put_u32(high);
        nr_puts(",\"pwm_enabled\":");nr_put_u32(enabled);nr_puts(",\"pwm_duty\":");
        if(valid)nr_put_u32(duty);else nr_puts("null");
        nr_puts(",\"restore_supported\":");nr_put_u32(valid&&enabled&&(high*100u)%period==0);nr_puts("}\n");return 1;
    }
    if(line_is(line,length,":link")) {
        nr_puts("NR_LINK {\"uart_baud\":");nr_put_u32(NR_UART_BAUD);
        nr_puts(",\"divider\":");nr_put_u32((NR_PLATFORM_CLOCK_HZ+NR_UART_BAUD/2)/NR_UART_BAUD);
        nr_puts(",\"framed_seen\":");nr_put_u32(nr_link_seen());
        nr_puts(",\"last_request_seq\":");nr_put_u32(nr_link_sequence());nr_puts("}\n");return 1;
    }
    if(line_is(line,length,":tools")) {
        /* A machine-readable capability manifest inspired by bounded tool schemas.
         * Availability is a snapshot; the dispatcher checks again on execution. */
        nr_puts("NR_TOOLS {\"schema\":3,\"max_utf8_bytes\":64,\"tools\":[{\"id\":0,\"name\":\"read_temp\",\"arguments\":{},\"available\":");
        nr_put_u32((NR_MMIO(0x10000100u)&7u)==5u);
        nr_puts("},{\"id\":1,\"name\":\"set_pwm\",\"duty_percent\":[0,100],\"frequency_hz\":1000,\"receipt\":\"period_high_enabled\"},{\"id\":2,\"name\":\"run_coremark\",\"iterations\":");nr_put_u32(NR_COREMARK_ITERATIONS);
        nr_puts("},{\"id\":3,\"name\":\"read_counter\",\"width_bits\":32},{\"id\":4,\"name\":\"set_led\",\"mask\":[0,255],\"bit\":[0,7],\"led7_available\":");
        nr_put_u32(!(NR_MMIO(0x1000003cu)&1u));nr_puts("}],\"multi_tool\":false,\"model_weights_bytes\":");nr_put_u32(NR_MODEL_WEIGHT_BYTES);nr_puts(",\"workspace_bytes\":");
        nr_put_u32(nr_model_workspace_bytes());nr_puts("}\n");return 1;
    }
    for(i=0;i<8 && i<length;i++)if(line[i]!=(uint8_t)prefix[i])break;
    if(i!=8 || length!=9 || line[8]<'0' || line[8]>'6') {
        nr_puts("NR_CONTROL_ERROR invalid_control\n");return 1;
    }
    *id=line[8]-'0';select_config(*id);return 1;
}
#endif
static void field(const char *key,uint32_t value) {
    nr_puts(key);nr_put_u32(value);
}
static void report_pmu(const nr_pmu_t *s) {
    field("\"cycles\":",s->cycles);field(",\"instret\":",s->instret);
    field(",\"branches\":",s->branches);field(",\"redirect_misses\":",s->redirect_misses);
    field(",\"mem_load_stall_cycles\":",s->mem_load_stall_cycles);
    field(",\"ic_misses\":",s->ic_misses);field(",\"dc_misses\":",s->dc_misses);
}
static void report(uint32_t case_id,uint32_t config,uint32_t mode,uint32_t graph,uint32_t dot4,const nr_prediction_t *p,
                   const nr_tool_request_t *r,uint32_t cycles,
                   nr_model_xnd_stats_t s,nr_exec_status_t execution,uint32_t value,
                   const nr_pmu_t *pmu,uint32_t tool_cycles,uint32_t request_cycles,
                   uint32_t decision_cycles,const nr_tool_receipt_t *receipt) {
    uint32_t i;
    nr_puts("NR_RESULT {\"case\":");nr_put_u32(case_id);
    field(",\"config\":",config);field(",\"graph\":",graph);field(",\"dot4\":",dot4);
    field(",\"mode\":",mode);field(",\"model_used\":",p?(p->encoder_used?1u:p->context_used?(p->context_hardware.used?3u:2u):0u):0u);
    field(",\"encoder_used\":",p?p->encoder_used:0);field(",\"context_used\":",p?p->context_used:0);
    field(",\"context_xnd_used\":",p?p->context_hardware.used:0);field(",\"context_hardware_macs\":",p?p->context_hardware_macs:0);
    nr_puts(",\"context_hardware\":");if(p&&p->context_hardware.used){nr_putc('{');field("\"loads\":",p->context_hardware.loads);field(",\"jobs\":",p->context_hardware.jobs);field(",\"dma_read_bytes\":",p->context_hardware.dma_read_bytes);field(",\"dma_write_bytes\":",p->context_hardware.dma_write_bytes);field(",\"engine_cycles\":",p->context_hardware.engine_cycles);field(",\"failures\":",p->context_hardware.failures);nr_putc('}');}else nr_puts("null");
    field(",\"context_deny\":",p?p->context_deny:0);field(",\"context_cycles\":",p?p->context_cycles:0);
    field(",\"encoder_cycles\":",p&&p->encoder_used?cycles-p->context_cycles:0);
    nr_puts(",\"context_logits\":");if(p&&p->context_used){nr_putc('[');nr_put_i32(p->context_logits[0]);nr_putc(',');nr_put_i32(p->context_logits[1]);nr_putc(']');}else nr_puts("null");
    nr_puts(",\"context_margin\":");if(p&&p->context_used)nr_put_i32(p->context_margin);else nr_puts("null");
    nr_puts(",\"context_threshold\":");if(p&&p->context_used)nr_put_i32(p->context_threshold);else nr_puts("null");
    field(",\"context_category\":",p?p->context_category:0);field(",\"context_bucket\":",p?p->context_bucket:5);field(",\"context_bucket_source\":",p?p->context_bucket_source:0);
    nr_puts(",\"context_category_logits\":");if(p&&p->context_used){nr_putc('[');for(i=0;i<9;i++){if(i)nr_putc(',');nr_put_i32(p->context_category_logits[i]);}nr_putc(']');}else nr_puts("null");
    field(",\"intent_repair_used\":",p?p->intent_repair_used:0);nr_puts(",\"intent_delta\":");if(p&&p->encoder_used){nr_putc('[');for(i=0;i<5;i++){if(i)nr_putc(',');nr_put_i32(p->intent_delta[i]);}nr_putc(']');}else nr_puts("null");
    nr_puts(",\"context_tool_logits\":");if(p&&p->context_used){nr_putc('[');for(i=0;i<5;i++){if(i)nr_putc(',');nr_put_i32(p->context_tool_logits[i]);}nr_putc(']');}else nr_puts("null");
    field(",\"intent_cascade_used\":",p?p->intent_cascade_used:0);nr_puts(",\"intent_cascade_delta\":");if(p&&p->encoder_used){nr_putc('[');for(i=0;i<5;i++){if(i)nr_putc(',');nr_put_i32(p->intent_cascade_delta[i]);}nr_putc(']');}else nr_puts("null");
    field(",\"fusion_used\":",p?p->fusion_used:0);field(",\"fusion_gate_margin\":",p?p->fusion_gate_margin:0);nr_puts(",\"fusion_delta\":");if(p&&p->encoder_used){nr_putc('[');for(i=0;i<5;i++){if(i)nr_putc(',');nr_put_i32(p->fusion_delta[i]);}nr_putc(']');}else nr_puts("null");
    field(",\"context_features\":",p?p->context_features:0);field(",\"context_scalar_macs\":",p?p->context_scalar_macs:0);
    nr_puts(",\"encoder_logits\":");if(p&&p->encoder_used){nr_putc('[');for(i=0;i<6;i++){if(i)nr_putc(',');nr_put_i32(p->encoder_logits[i]);}nr_putc(']');}else nr_puts("null");
    field(",\"decision_cycles\":",decision_cycles);
    nr_puts(",\"tool\":");if(p&&p->encoder_used)nr_put_u32(p->tool);else nr_puts("null");
    field(",\"selected_tool\":",r->tool);
    nr_puts(",\"margin\":");if(p&&p->encoder_used)nr_put_i32(p->margin);else nr_puts("null");
    field(",\"confidence_threshold\":",NR_MIN_CONFIDENCE_MARGIN);
    field(",\"decode\":",r->status);field(",\"argument\":",(uint32_t)r->argument);
    field(",\"operation\":",r->operation);field(",\"selection_source\":",r->selection_source);
    field(",\"cycles\":",cycles);field(",\"loads\":",s.loads);
    field(",\"jobs\":",s.jobs);field(",\"reuses\":",s.reuses);
    field(",\"activation_bytes\":",s.activation_dma_bytes);
    field(",\"weight_bytes\":",s.weight_dma_bytes);
    field(",\"bias_bytes\":",s.bias_dma_bytes);
    field(",\"residual_bytes\":",s.residual_dma_bytes);
    field(",\"output_bytes\":",s.output_dma_bytes);
    field(",\"engine_cycles\":",s.hardware_cycles);
    field(",\"failures\":",s.failures);field(",\"execute\":",execution);
    nr_puts(",\"value\":");
    if(r->tool==NR_READ_TEMP) nr_put_i32((int32_t)value); else nr_put_u32(value);
    nr_puts(",\"logits\":");
    if(p&&p->encoder_used){nr_putc('[');for(i=0;i<6;i++) {if(i)nr_putc(',');nr_put_i32(p->logits[i]);}nr_putc(']');}
    else nr_puts("null");
    field(",\"tool_cycles\":",tool_cycles);
    field(",\"request_cycles\":",request_cycles);
    nr_puts(",\"pmu\":");if(p&&p->encoder_used){nr_putc('{');report_pmu(pmu);nr_putc('}');}else nr_puts("null");
    nr_puts(",\"receipt\":");
    if(receipt&&receipt->kind) {
        nr_putc('{');field("\"kind\":",receipt->kind);field(",\"requested\":",receipt->requested);
        field(",\"readback\":",receipt->readback);field(",\"match\":",receipt->match);
        field(",\"period\":",receipt->period);field(",\"high\":",receipt->high);field(",\"enabled\":",receipt->enabled);
        field(",\"adc_status\":",receipt->adc_status);field(",\"adc_raw\":",receipt->adc_raw);nr_putc('}');
    }else nr_puts("null");
    nr_puts("}\n");
}
#ifndef NR_MODEL_SELFTEST
static void compact(uint32_t id,uint32_t config,const nr_tool_request_t *r,nr_exec_status_t execution,
                    uint32_t value,uint32_t decision,uint32_t tool,uint32_t request,const nr_tool_receipt_t *receipt,const nr_prediction_t *p) {
    uint32_t i;
    uint32_t a[31]={p->context_hardware.used?3u:p->context_used?2u:1u,id,config,r->tool,r->status,(uint32_t)r->argument,r->operation,r->selection_source,
        execution,value,decision,tool,request,receipt->kind,receipt->requested,receipt->readback,receipt->match,
        receipt->period,receipt->high,receipt->enabled,p->context_used,p->context_deny,(uint32_t)p->context_logits[0],(uint32_t)p->context_logits[1],(uint32_t)p->context_threshold,
        p->context_hardware.used,p->context_hardware.loads,p->context_hardware.jobs,p->context_hardware.dma_read_bytes,p->context_hardware.dma_write_bytes,p->context_hardware.engine_cycles};
    nr_puts("NR_FAST [");
    for(i=0;i<(p->context_hardware.used?31u:p->context_used?25u:20u);i++){if(i)nr_putc(',');if((i==9&&r->tool==NR_READ_TEMP)||i==22||i==23||i==24)nr_put_i32((int32_t)a[i]);else nr_put_u32(a[i]);}
    nr_puts("]\n");
}
#endif
#if NR_MODEL_PROFILE
static void report_profile(uint32_t config,uint32_t case_id,uint32_t total) {
    static const char *names[]={"embedding","qkv","qk","exp","av_div","post","pool_head","copy"};
    nr_model_profile_t profile;uint32_t i;
    nr_model_profile_get(&profile);
    nr_puts("NR_PROFILE {\"config\":");nr_put_u32(config);
    field(",\"case\":",case_id);field(",\"instrumented_total_cycles\":",total);
    nr_puts(",\"stages\":{");
    for(i=0;i<NR_PROFILE_STAGES;i++) {
        if(i) {nr_putc(',');}
        nr_putc('"');nr_puts(names[i]);nr_puts("\":{");
        field("\"cycles\":",profile.cycles[i]);field(",\"intervals\":",profile.intervals[i]);nr_putc('}');
    }
    nr_puts("}}\n");
}
#else
#define report_profile(config,case_id,total)
#endif
static int infer(const uint8_t *text,uint32_t length,nr_prediction_t *p,
                 nr_tool_request_t *r,uint32_t *cycles,nr_pmu_t *pmu,const nr_context_t *context) {
#if NR_MODEL_PROFILE
    nr_model_profile_reset();
#endif
    nr_context_t local;uint32_t context_cycles=0;
    if(!context){uint32_t c=nr_cycle();if(nr_model_context(text,length,&local))return -1;context_cycles=nr_cycle()-c;context=&local;}
    nr_pmu_t a,b;nr_pmu_snapshot(&a);
    uint32_t begin=nr_cycle();
    int status=nr_model_predict_with_context(text,length,p,context);
    *cycles=nr_cycle()-begin+context_cycles;
    p->context_cycles=context_cycles; /* A supplied preliminary head is added by the caller. */
    nr_pmu_snapshot(&b);*pmu=nr_pmu_delta(&a,&b); /* Encoder bracket only, no context head. */
    if(status) return status;
    nr_tool_decode_prediction(text,length,p,r);return 0;
}
int main(void) {
    nr_puts("NeedleRV-X BRAM64; workspace=");nr_put_u32(nr_model_workspace_bytes());
    nr_puts("; clock_hz=");nr_put_u32(NR_PLATFORM_CLOCK_HZ);nr_puts("\n");
    nr_puts("NR_BUILD {\"protocol\":6,\"firmware\":\"");
    nr_puts(NR_PLATFORM_CLOCK_HZ==27000000u?"experimental_position_fusion_oct30":"experimental_position_fusion_oct30");
    nr_puts(NR_MODEL_ENGRAM_ENABLED?"\",\"model_stage\":\"unicode_ngram_memory_oct29\",\"kernel_stage\":\"xnd_post_fetch_oct29\"":"\",\"model_stage\":\"tool_contract_replay_oct28\",\"kernel_stage\":\"xnd_post_fetch_oct29\"");
    nr_puts(",\"formal_fast\":1,\"neural_timing\":\"context_plus_encoder\"");field(",\"context_head\":",NR_MODEL_CONTEXT_ENABLED);field(",\"context_weights_bytes\":",NR_MODEL_CONTEXT_BYTES);field(",\"context_hidden\":",NR_MODEL_CONTEXT_HIDDEN);field(",\"context_outputs\":",NR_MODEL_CONTEXT_OUTPUTS);field(",\"intent_cascade\":",1);field(",\"semantic_calibration_revision\":",3);field(",\"position_features\":",2048);field(",\"semantic_weight_cache\":",NR_RESOURCE_CACHE_BACKEND);field(",\"sram_bytes\":",524288);field(",\"fusion_weights_bytes\":",NR_MODEL_FUSION_BYTES);field(",\"context_classes\":",9);field(",\"intent_repair\":",1);field(",\"context_xnd\":",1);field(",\"context_xnd_min_features\":",24);field(",\"semantic_memory\":",NR_MODEL_ENGRAM_ENABLED);field(",\"model_weights_bytes\":",NR_MODEL_WEIGHT_BYTES);field(",\"memory_weights_bytes\":",NR_MODEL_MEMORY_BYTES);
    field(",\"core_count\":",2);field(",\"clock_hz\":",NR_PLATFORM_CLOCK_HZ);field(",\"uart_baud\":",NR_UART_BAUD);field(",\"coremark_iterations\":",NR_COREMARK_ITERATIONS);nr_puts(",\"max_utf8_bytes\":64,\"confidence_threshold\":16");
    field(",\"tool_schema\":",2);field(",\"q_reuse\":",NR_OPT_Q_REUSE);field(",\"av4\":",NR_OPT_AV4);
    field(",\"post_fuse\":",NR_OPT_POST_FUSE);field(",\"xnd_postprocess\":",NR_OPT_XND_POSTPROCESS);field(",\"profile\":",NR_MODEL_PROFILE);nr_puts(",\"capabilities\":{\"fast\":1,\"compact\":1,\"io_snapshot\":1,\"receipt\":1,\"framed_rpc\":1,\"tool_manifest\":1}}\n");
#if NR_MODEL_PROFILE
    {
        uint32_t i,sum=0;
        /* 两次相邻计数读取包含call/CSR开销，单独报告，不能称零开销。 */
        for(i=0;i<32;i++) {uint32_t a=nr_cycle();sum+=nr_cycle()-a;}
        nr_puts("NR_PROFILE_OVERHEAD {\"pairs\":32,\"pair_cycles_sum\":");nr_put_u32(sum);nr_puts("}\n");
    }
#endif
#ifdef NR_MODEL_SELFTEST
    static const char *cases[]={"led 37","pwm -1","hello","读取计数器"};
    /* graph=1时所有硬件策略都使用相同的两token交错图，保证对照公平。 */
    nr_prediction_t baseline[4];
#if NR_MODEL_PROFILE
    uint32_t have_baseline[4]={0,0,0,0};
#endif
    uint32_t config,id,i,cycles,value;
    for(config=0;config<sizeof(configs)/sizeof(configs[0]);config++) {
#if NR_MODEL_PROFILE
        if(config<5) continue; /* 粗粒度热点只测同图scalar/dot4，不重复28路径。 */
#endif
        nr_model_xnd_set_mode((nr_xnd_mode_t)configs[config].mode);
        nr_model_set_qkv_interleaved(configs[config].graph);
        nr_model_set_attention_dot4(configs[config].dot4);
        for(id=0;id<4;id++) {
#if NR_MODEL_PROFILE
            if(id!=0 && id!=3) continue;
#endif
            nr_prediction_t p;nr_tool_request_t r;nr_exec_status_t executed;
            nr_pmu_t pmu={0};uint32_t request_begin,tool_begin,tool_cycles,request_cycles;
            nr_model_xnd_reset_stats();
            request_begin=nr_cycle();
            if(infer((const uint8_t *)cases[id],nr_length(cases[id]),&p,&r,&cycles,&pmu,0)) {
                nr_puts("MODEL_ERROR backend\n");NR_LED=0xee;return 1;
            }
#if NR_MODEL_PROFILE
            if(!have_baseline[id]) {baseline[id]=p;have_baseline[id]=1;}
#else
            if(config==0) baseline[id]=p;
#endif
            else for(i=0;i<6;i++) if(p.logits[i]!=baseline[id].logits[i]) {
                nr_puts("MODEL_ERROR numeric mismatch\n");NR_LED=0xee;return 1;
            }
            tool_begin=nr_cycle();executed=nr_tool_execute(&r,&value);
            tool_cycles=nr_cycle()-tool_begin;request_cycles=nr_cycle()-request_begin;
            report(id,config,configs[config].mode,configs[config].graph,configs[config].dot4,
                   &p,&r,cycles,nr_model_xnd_stats(),executed,value,&pmu,tool_cycles,request_cycles,request_cycles-tool_cycles,0);
            report_profile(config,id,cycles);
            if((id==0 && (executed!=NR_EXEC_OK || NR_LED!=37)) ||
               ((id==1 || id==2) && (executed!=NR_EXEC_DENIED || NR_LED!=37)) ||
               (id==3 && (executed!=NR_EXEC_OK || !value || NR_LED!=37))) {
                nr_puts("MODEL_ERROR tool side effect\n");NR_LED=0xee;return 1;
            }
        }
    }
    nr_puts("NR_MODEL_PASS\n");NR_LED=0xc0;
#else
    uint8_t line[64];uint32_t sequence=0,active_config=6,suppress_ready=0;
    select_config(active_config);report_fast_mode();report_format();
    for(;;) {
        nr_prediction_t p;nr_tool_request_t r;uint32_t cycles=0,value,model_used=1,decision_cycles;nr_tool_receipt_t receipt;
        nr_pmu_t pmu={0};uint32_t request_begin,tool_begin,tool_cycles,request_cycles;
        nr_link_request_t link;int length;
        if(!suppress_ready)nr_puts("NR_READY\n");
        suppress_ready=0;length=nr_link_read(line,sizeof(line),&link);
        if(length<0) {
            nr_puts("NR_INPUT_ERROR ");
            nr_puts(length==NR_INPUT_TOO_LONG?"too_long":length==NR_INPUT_CRC?"frame_crc":length==NR_INPUT_TIMEOUT?"frame_timeout":length==NR_INPUT_SEQUENCE?"stale_sequence":length==NR_INPUT_UTF8?"invalid_utf8":"bad_frame");
            nr_putc('\n');continue;
        }
        if(control_config(line,(uint32_t)length,&active_config)) continue;
        if(!length) {nr_puts("NR_INPUT_ERROR empty\n");continue;}
        nr_model_xnd_reset_stats();
        request_begin=nr_cycle();
        nr_context_t context={0};uint32_t context_cycles=0;
        if(fast_enabled&&nr_tool_decode_machine(line,(uint32_t)length,&r)==NR_FAST_HANDLED) {
            nr_prediction_set_context(&p,&context);model_used=0;
        } else {
            uint32_t context_begin=nr_cycle();
            {int context_status=nr_model_context(line,(uint32_t)length,&context);if(context_status==NR_GEMV_FATAL){nr_puts("NR_BACKEND_ERROR reset_required\n");NR_LED=0xee;return 1;}if(context_status){nr_puts("NR_INPUT_ERROR invalid_utf8\n");continue;}}
            context_cycles=nr_cycle()-context_begin;nr_prediction_set_context(&p,&context);
            if(fast_enabled&&nr_tool_decode_fast_with_context(line,(uint32_t)length,&r,&context)==NR_FAST_HANDLED){nr_prediction_set_context(&p,&context);model_used=context.used?(context.hardware.used?3u:2u):0u;}
            else if(infer(line,(uint32_t)length,&p,&r,&cycles,&pmu,&context)) {
                nr_puts("NR_BACKEND_ERROR reset_required\n");NR_LED=0xee;return 1;
            }
        }
        p.context_cycles=context_cycles;if(p.encoder_used)cycles+=context_cycles;else cycles=p.context_used?context_cycles:0;
        decision_cycles=nr_cycle()-request_begin;
        /* A long tool must not hide an already completed inference. No success
           is announced here. Exclude this optional notification's UART time
           from the computation/dispatch request interval. */
        if(r.status==NR_TOOL_OK && r.tool==NR_RUN_COREMARK) {
            uint32_t notify_begin=nr_cycle();
            nr_puts("NR_ACTION {\"phase\":\"tool_start\"");
            field(",\"case\":",sequence);field(",\"config\":",active_config);
            field(",\"model_used\":",model_used);field(",\"encoder_used\":",p.encoder_used);field(",\"context_used\":",p.context_used);field(",\"context_xnd_used\":",p.context_hardware.used);field(",\"context_deny\":",p.context_deny);field(",\"context_cycles\":",p.context_cycles);field(",\"encoder_cycles\":",p.encoder_used?cycles-p.context_cycles:0);
            nr_puts(",\"context_logits\":[");nr_put_i32(p.context_logits[0]);nr_putc(',');nr_put_i32(p.context_logits[1]);nr_putc(']');field(",\"context_threshold\":",(uint32_t)p.context_threshold);nr_puts(",\"tool\":");if(p.encoder_used)nr_put_u32(p.tool);else nr_puts("null");field(",\"selected_tool\":",r.tool);
            field(",\"cycles\":",cycles);field(",\"decision_cycles\":",decision_cycles);field(",\"decode\":",r.status);
            field(",\"selection_source\":",r.selection_source);nr_puts("}\n");
            request_begin+=nr_cycle()-notify_begin;
        }
        tool_begin=nr_cycle();nr_exec_status_t execution=nr_tool_execute_receipt(&r,&value,&receipt);
        tool_cycles=nr_cycle()-tool_begin;request_cycles=nr_cycle()-request_begin;
        if(!link.framed&&!p.encoder_used&&compact_enabled)compact(sequence,active_config,&r,execution,value,decision_cycles,tool_cycles,request_cycles,&receipt,&p);
        else if(!link.framed||p.encoder_used)report(sequence,active_config,configs[active_config].mode,configs[active_config].graph,
               configs[active_config].dot4,&p,&r,cycles,nr_model_xnd_stats(),execution,value,&pmu,tool_cycles,request_cycles,decision_cycles,&receipt);
        if(p.encoder_used){report_profile(active_config,sequence,cycles);}
        if(link.framed) {
            nr_link_result(sequence,active_config,&r,execution,value,decision_cycles,tool_cycles,request_cycles,&receipt,link.sequence,model_used,p.context_used,p.context_deny,p.context_hardware.used);
            suppress_ready=1;
        }
        sequence++;
    }
#endif
    return 0;
}
