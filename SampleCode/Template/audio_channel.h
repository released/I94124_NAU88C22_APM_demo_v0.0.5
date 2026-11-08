#ifndef AUDIO_CHANNEL_H
#define AUDIO_CHANNEL_H

#include <stdint.h>

/* Stereo transport: low 16 bits = left; high 16 bits = right. */
static uint32_t Audio_PackStereo(uint16_t left, uint16_t right)
{
    return (uint32_t)left | ((uint32_t)right << 16);
}

#endif
