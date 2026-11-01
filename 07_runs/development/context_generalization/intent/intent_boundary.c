#include "byte_tool_model.h"
#include "byte_context.c.inc"
#include "intent_runtime.inc"
int run_intent(const uint8_t*b,uint32_t n,int32_t*out){int status=nr_ctx_features(b,n);if(status)return status;nr_intent_delta(out);return 0;}
int run_repair(int32_t*z,int32_t*delta){return nr_intent_repair(z,delta);}
