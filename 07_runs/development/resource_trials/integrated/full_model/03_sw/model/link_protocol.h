#ifndef NR_LINK_PROTOCOL_H
#define NR_LINK_PROTOCOL_H
#include "tool_dispatch.h"
typedef struct {uint32_t framed,sequence;} nr_link_request_t;
enum {NR_INPUT_TOO_LONG=-1,NR_INPUT_FRAME=-2,NR_INPUT_CRC=-3,NR_INPUT_TIMEOUT=-4,NR_INPUT_SEQUENCE=-5,NR_INPUT_UTF8=-6};
int nr_link_utf8_valid(const uint8_t *buffer,uint32_t length);
int nr_link_read(uint8_t *buffer,uint32_t capacity,nr_link_request_t *meta);
uint32_t nr_link_seen(void);
uint32_t nr_link_sequence(void);
void nr_link_result(uint32_t case_id,uint32_t config,const nr_tool_request_t *request,
 nr_exec_status_t execution,uint32_t value,uint32_t decision,uint32_t tool_cycles,
 uint32_t request_cycles,const nr_tool_receipt_t *receipt,uint32_t sequence,uint32_t model_used,uint32_t context_used,uint32_t context_deny,uint32_t context_xnd_used);
#endif
