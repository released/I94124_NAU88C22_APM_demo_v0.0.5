//colsonic_def.c
#include "colsonic_def.h"
#include "colsonic_apm.h"

volatile __attribute__((aligned(4))) unsigned char APM_MemPool[COLSONIC_BUF_LEN_MODE] = {0};
unsigned int colsonic_lib_buf_len = COLSONIC_BUF_LEN_MODE;


