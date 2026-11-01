#include <stdio.h>
#include <string.h>
#include "byte_tool_model.h"
int main(void){char b[512];while(fgets(b,sizeof b,stdin)){size_t n=strlen(b);while(n&&(b[n-1]==10||b[n-1]==13))b[--n]=0;nr_tool_request_t q;memset(&q,0,sizeof(q));int h=nr_tool_decode_machine((uint8_t*)b,n,&q);printf("%d %d %d %d %d %d",h,q.tool,q.status,q.argument,q.operation,q.selection_source);putchar(10);}return 0;}
