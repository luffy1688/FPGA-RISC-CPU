#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
int main(void){char b[1024];nr_tool_request_t r;nr_context_t c={0};c.used=1;while(fgets(b,sizeof(b),stdin)){size_t n=strlen(b);if(n&&b[n-1]=='\n')n--;int h=nr_tool_decode_fast_with_context((const uint8_t*)b,(uint32_t)n,&r,&c);printf("%d %d %d %d %d\n",h,(int)r.tool,r.argument,(int)r.operation,(int)r.status);}return 0;}
