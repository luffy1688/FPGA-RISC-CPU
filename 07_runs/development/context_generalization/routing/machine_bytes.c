#include <assert.h>
#include "byte_tool_model.h"
int main(void){nr_tool_request_t r;
static const unsigned char a[]={108,101,100,32,51,55,0},b[]={114,101,97,100,32,116,101,109,112,0,105},c[]={108,101,100,32,51,55,192,175},d[]={108,101,100,32,51,55,237,160,128},e[]={108,101,100,32,51,55,244,144,128,128};
assert(!nr_tool_decode_machine(a,sizeof a,&r));assert(!nr_tool_decode_machine(b,sizeof b,&r));assert(!nr_tool_decode_machine(c,sizeof c,&r));assert(!nr_tool_decode_machine(d,sizeof d,&r));assert(!nr_tool_decode_machine(e,sizeof e,&r));return 0;}
