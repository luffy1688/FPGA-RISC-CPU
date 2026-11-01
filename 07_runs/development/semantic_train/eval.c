#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
int main(void){char b[512];while(fgets(b,sizeof b,stdin)){size_t n=strlen(b);while(n&&(b[n-1]=='\n'||b[n-1]=='\r'))b[--n]=0;nr_prediction_t p;nr_tool_request_t q;if(nr_model_predict((const uint8_t*)b,n,&p)){puts("{\"error\":1}");continue;}nr_tool_decode_prediction((const uint8_t*)b,n,&p,&q);printf("{\"index\":%d,\"margin\":%d,\"selected\":%d,\"status\":%d,\"argument\":%d,\"operation\":%d,\"source\":%d,\"logits\":[%d,%d,%d,%d,%d,%d]}\n",p.tool,p.margin,q.tool,q.status,q.argument,q.operation,q.selection_source,p.logits[0],p.logits[1],p.logits[2],p.logits[3],p.logits[4],p.logits[5]);}return 0;}
