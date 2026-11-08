#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "audio_channel.h"

#define COLSONIC_DAT_LEN 320
#define PDMA_IRQn 0
#define FALSE 0
#define TRUE 1

/* Only the fields consumed by the actual extracted processing functions. */
typedef struct
{
    uint16_t *pu16Near;
    uint16_t *pu16Far;
    uint16_t u16DecodeTmp[COLSONIC_DAT_LEN];
    uint32_t u32Decode[2][COLSONIC_DAT_LEN];
    uint16_t u16DecodeAvalCnt;
    uint8_t u8Decode_Buf_Idx;
    uint8_t bNearReady;
    uint8_t bDoAECReady;
    uint8_t bByPass;
} TEST_DATA_MANAGER;

static TEST_DATA_MANAGER g_sDataManager;
static uint16_t near_data[COLSONIC_DAT_LEN];
static uint16_t far_data[COLSONIC_DAT_LEN];
static unsigned int apm_calls;

static void NVIC_DisableIRQ(int irq) { (void)irq; }
static void NVIC_EnableIRQ(int irq) { (void)irq; }

/* Deterministic output for transport testing; not an AEC/NS implementation. */
static void Colsonic_apm_proc(int16_t *near_in, int16_t *far_in, int16_t *out)
{
    unsigned int i;
    assert(near_in == (int16_t *)near_data);
    assert(far_in == (int16_t *)far_data);
    for (i = 0; i < COLSONIC_DAT_LEN; i++)
        out[i] = (int16_t)(0x9000u + i);
    apm_calls++;
}

#include "work_i2c.inc"
#include "work_usb.inc"

static void ResetData(void)
{
    unsigned int i;
    memset(&g_sDataManager, 0, sizeof(g_sDataManager));
    for (i = 0; i < COLSONIC_DAT_LEN; i++)
    {
        near_data[i] = (uint16_t)(0x8000u ^ (i * 73u));
        far_data[i] = (uint16_t)(0x1234u ^ (i * 31u));
    }
    near_data[0] = 0;
    near_data[1] = 0xFFFFu;
    near_data[2] = 0x8000u;
    near_data[3] = 0x7FFFu;
    g_sDataManager.pu16Near = near_data;
    g_sDataManager.pu16Far = far_data;
    apm_calls = 0;
}

static void CheckRow(unsigned int row, int bypass)
{
    unsigned int i;
    uint32_t word;
    for (i = 0; i < COLSONIC_DAT_LEN; i++)
    {
        word = g_sDataManager.u32Decode[row][i];
        if (bypass)
        {
            assert((word & 0xFFFFu) == far_data[i]);
            assert((word >> 16) == near_data[i]);
        }
        else
        {
            assert((word & 0xFFFFu) == near_data[i]);
            assert((word >> 16) == (0x9000u + i));
        }
    }
}

static void TestNormal(void (*work)(void), int usb)
{
    ResetData();
    work();
    assert(apm_calls == 0);
    g_sDataManager.bByPass = TRUE; /* USB must have no bypass path. */
    if (!usb)
        g_sDataManager.bByPass = FALSE;
    g_sDataManager.bNearReady = TRUE;
    g_sDataManager.bDoAECReady = TRUE;
    work();
    assert(apm_calls == 1);
    assert(g_sDataManager.u16DecodeAvalCnt == 320);
    assert(g_sDataManager.u8Decode_Buf_Idx == 1);
    CheckRow(0, FALSE);
    g_sDataManager.bNearReady = TRUE;
    g_sDataManager.bDoAECReady = TRUE;
    work();
    assert(apm_calls == 2);
    assert(g_sDataManager.u16DecodeAvalCnt == 640);
    assert(g_sDataManager.u8Decode_Buf_Idx == 0);
    CheckRow(1, FALSE);
}

int main(void)
{
    assert(Audio_PackStereo(0x1111u, 0x3333u) == 0x33331111u);
    assert(Audio_PackStereo(0xFFFFu, 0x8000u) == 0x8000FFFFu);
    TestNormal(WorkI2C, FALSE);
    TestNormal(WorkUSB, TRUE);
    ResetData();
    g_sDataManager.bByPass = TRUE;
    g_sDataManager.bNearReady = TRUE;
    WorkI2C();
    assert(apm_calls == 1); /* Output bypass still runs the APM. */
    assert(g_sDataManager.u16DecodeAvalCnt == 320);
    CheckRow(0, TRUE);
    puts("PASS: actual I2C/USB frame packing, 320 samples, signed PCM bits, bypass and row rotation");
    return 0;
}
