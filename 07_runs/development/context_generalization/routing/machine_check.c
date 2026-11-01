#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
int main(void){char b[1024];nr_tool_request_t r;while(fgets(b,sizeof(b),stdin)){size_t n=strlen(b);if(n&&b[n-1]=='\n')n--;int h=nr_tool_decode_machine((const uint8_t*)b,(uint32_t)n,&r);printf("%d %d %d %d\n",h,h?(int)r.tool:-1,h?r.argument:-1,h?(int)r.status:-1);}return 0;}
