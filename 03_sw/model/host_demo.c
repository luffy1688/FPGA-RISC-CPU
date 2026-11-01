/* host_demo只给服务器查看模型行为，FPGA工程不要链接这个printf入口。 */
#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
int main(int argc,char **argv) {
    nr_prediction_t p;
    nr_tool_request_t r;
    uint32_t i;
    if(argc!=2) { fprintf(stderr,"usage: model_demo \"set pwm 63\"\n");return 2; }
    if(nr_model_predict((const uint8_t *)argv[1],strlen(argv[1]),&p)) return 2;
    nr_tool_decode_prediction((const uint8_t *)argv[1],strlen(argv[1]),&p,&r);
    printf("{\"intent\":\"%s\",\"index\":%u,\"logits\":[",nr_tool_name(p.tool),(unsigned)p.tool);
    for(i=0;i<6;i++) printf("%s%d",i?",":"",p.logits[i]);
    printf("],\"encoder_logits\":[");for(i=0;i<6;i++)printf("%s%d",i?",":"",p.encoder_logits[i]);
    printf("],\"context_logits\":[%d,%d],\"context_used\":%u,\"context_deny\":%u,\"context_margin\":%d,\"context_threshold\":%d,\"encoder_used\":%u",
           p.context_logits[0],p.context_logits[1],p.context_used,p.context_deny,p.context_margin,p.context_threshold,p.encoder_used);
    printf(",\"margin\":%d,\"status\":%d,\"argument\":%d,\"workspace_bytes\":%u,"
           "\"selected_index\":%u,\"operation\":%u,\"selection_source\":%u}\n",
           p.margin,(int)r.status,r.argument,nr_model_workspace_bytes(),
           (unsigned)r.tool,(unsigned)r.operation,(unsigned)r.selection_source);
    return 0;
}
