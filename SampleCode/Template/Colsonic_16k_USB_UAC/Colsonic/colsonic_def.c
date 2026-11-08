//colsonic_def.c
#include "colsonic_def.h"
#include "colsonic_apm.h"

#include "alg_type.h"

volatile __attribute__((aligned(4))) unsigned char APM_MemPool[COLSONIC_BUF_LEN_MODE] = {0};
unsigned int colsonic_lib_buf_len = COLSONIC_BUF_LEN_MODE;
unsigned int  colsonic_lib_aec_len =  COLSONIC_AEC_LEN ;



unsigned int mic_module_num = 6;
unsigned int sp_module_num = 0;

module_id_type_t  mic_module_id[]={
PRE_AEC_MODULE,
PRE_NS_MODULE,
POST_AEC_MODULE,
EQ_MODULE,
GAIN_MODULE,
DRC_MODULE,
}  ;
module_id_type_t  sp_module_id[]={
END_MODULE_TYPE_NUM,
}  ;
