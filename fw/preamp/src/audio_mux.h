/*
 * AmpliPi Home Audio
 * Copyright (C) 2021 MicroNova LLC
 *
 * Configure each of the preamp controller's six zones.
 * Each zone has four configurable properties:
 *   - Attenuation
 *   - Standby
 *   - Mute
 *   - Audio Source
 *
 * Also controls each of the 4 audio sources.
 * Each source can have an analog or digital source selected as its input.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#ifndef AUDIO_MUX_H_
#define AUDIO_MUX_H_

// Uncomment this line to enable automatic mute control via high/low volume.
// #define AUTO_MUTE_CTRL

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef enum
{
  IT_ANALOG,
  IT_DIGITAL
} InputType;

bool isOn(size_t zone);
bool anyOn();

void mute(size_t zone, bool mute);
bool muted(size_t zone);
void standby(bool standby);
bool inStandby();

void    initZones();
void    setZoneVolume(size_t zone, uint8_t vol);
uint8_t getZoneVolume(size_t zone);
void    setZoneSource(size_t zone, size_t src);
size_t  getZoneSource(size_t zone);

void      initSources();
void      setSourceAD(size_t src, InputType type);
InputType getSourceAD(size_t src);

#endif /* AUDIO_MUX_H_ */
