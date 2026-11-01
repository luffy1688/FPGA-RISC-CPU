#ifndef NR_SEMANTIC_CACHED_H
#define NR_SEMANTIC_CACHED_H
#include "semantic_xnd.h"
int nr_semantic_cached_gemv(const int8_t*,const int32_t*,const int8_t*,const int32_t*,const int16_t*,const uint16_t*,uint32_t,uint32_t,uint32_t,int32_t*,int8_t*,nr_semantic_stats_t*);
uint32_t nr_semantic_cached_last_macs(void);
uint32_t nr_semantic_cached_workspace_bytes(void);
#endif
