/**
 * The AI interviewer, drawn on a canvas (so it is part of the recorded video).
 * An illustrated person: blinks, sways slightly, and opens the mouth with the voice level.
 */

import type { Interviewer } from '@/lib/api'

interface Look {
  skin: string
  skinShade: string
  hair: string
  suit: string
  shirt: string
  backdrop: [string, string]
  longHair: boolean
}

const LOOKS: Record<Interviewer, Look> = {
  maya: {
    skin: '#e8b896',
    skinShade: '#d39d7a',
    hair: '#3b2418',
    suit: '#2f3e63',
    shirt: '#f3f4f6',
    backdrop: ['#dfe7f3', '#b9c7de'],
    longHair: true,
  },
  james: {
    skin: '#c58c64',
    skinShade: '#a8734f',
    hair: '#1f1a17',
    suit: '#3a3f47',
    shirt: '#dbe6f5',
    backdrop: ['#e4e9ee', '#c3ccd6'],
    longHair: false,
  },
}

export interface AvatarState {
  level: number // 0..1 voice loudness
  speaking: boolean
  thinking: boolean
  time: number // ms
}

/** Blink roughly every 4 s for 150 ms, deterministic from time. */
function blinkAmount(time: number): number {
  const cycle = time % 4200
  return cycle < 150 ? Math.sin((cycle / 150) * Math.PI) : 0
}

export function drawInterviewer(ctx: CanvasRenderingContext2D, w: number, h: number, who: Interviewer, s: AvatarState) {
  const look = LOOKS[who]
  // Backdrop: soft office wall with a window glow and a shelf line.
  const bg = ctx.createLinearGradient(0, 0, 0, h)
  bg.addColorStop(0, look.backdrop[0])
  bg.addColorStop(1, look.backdrop[1])
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, w, h)
  const glow = ctx.createRadialGradient(w * 0.82, h * 0.25, 10, w * 0.82, h * 0.25, w * 0.35)
  glow.addColorStop(0, 'rgba(255,255,255,0.55)')
  glow.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = glow
  ctx.fillRect(0, 0, w, h)
  ctx.fillStyle = 'rgba(80,90,110,0.12)'
  ctx.fillRect(w * 0.06, h * 0.36, w * 0.22, h * 0.012)
  ctx.fillRect(w * 0.08, h * 0.28, w * 0.03, h * 0.08)
  ctx.fillRect(w * 0.12, h * 0.31, w * 0.025, h * 0.05)

  const u = h / 100 // unit: 1% of height
  const sway = Math.sin(s.time / 1400) * u * (s.speaking ? 0.6 : 0.3)
  const nod = s.speaking ? Math.sin(s.time / 380) * u * 0.35 : 0
  const cx = w / 2 + sway
  const headY = h * 0.42 + nod

  ctx.save()
  // Shoulders and jacket.
  ctx.fillStyle = look.suit
  ctx.beginPath()
  ctx.moveTo(cx - 34 * u, h)
  ctx.bezierCurveTo(cx - 33 * u, h * 0.78, cx - 22 * u, h * 0.7, cx - 9 * u, h * 0.68)
  ctx.lineTo(cx + 9 * u, h * 0.68)
  ctx.bezierCurveTo(cx + 22 * u, h * 0.7, cx + 33 * u, h * 0.78, cx + 34 * u, h)
  ctx.closePath()
  ctx.fill()
  // Shirt collar V.
  ctx.fillStyle = look.shirt
  ctx.beginPath()
  ctx.moveTo(cx - 8 * u, h * 0.68)
  ctx.lineTo(cx, h * 0.82)
  ctx.lineTo(cx + 8 * u, h * 0.68)
  ctx.closePath()
  ctx.fill()
  // Lapels.
  ctx.strokeStyle = 'rgba(0,0,0,0.18)'
  ctx.lineWidth = u * 0.5
  ctx.beginPath()
  ctx.moveTo(cx - 8 * u, h * 0.68)
  ctx.lineTo(cx - 3 * u, h * 0.86)
  ctx.moveTo(cx + 8 * u, h * 0.68)
  ctx.lineTo(cx + 3 * u, h * 0.86)
  ctx.stroke()

  // Neck.
  ctx.fillStyle = look.skinShade
  ctx.fillRect(cx - 5 * u, headY + 12 * u, 10 * u, 12 * u)

  // Long hair behind the head.
  if (look.longHair) {
    ctx.fillStyle = look.hair
    ctx.beginPath()
    ctx.ellipse(cx, headY + 4 * u, 17 * u, 22 * u, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillRect(cx - 17 * u, headY + 2 * u, 34 * u, 20 * u)
  }

  // Head.
  ctx.fillStyle = look.skin
  ctx.beginPath()
  ctx.ellipse(cx, headY, 13.5 * u, 16.5 * u, 0, 0, Math.PI * 2)
  ctx.fill()
  // Ears.
  ctx.beginPath()
  ctx.ellipse(cx - 13.5 * u, headY + 1 * u, 2 * u, 3.2 * u, 0, 0, Math.PI * 2)
  ctx.ellipse(cx + 13.5 * u, headY + 1 * u, 2 * u, 3.2 * u, 0, 0, Math.PI * 2)
  ctx.fill()

  // Hair on top.
  ctx.fillStyle = look.hair
  ctx.beginPath()
  if (look.longHair) {
    ctx.ellipse(cx, headY - 9 * u, 14.5 * u, 9.5 * u, 0, Math.PI, Math.PI * 2)
    ctx.quadraticCurveTo(cx + 6 * u, headY - 9 * u, cx - 2 * u, headY - 12 * u)
    ctx.quadraticCurveTo(cx - 9 * u, headY - 6 * u, cx - 14.5 * u, headY - 4 * u)
  } else {
    ctx.ellipse(cx, headY - 10 * u, 14 * u, 8 * u, 0, Math.PI, Math.PI * 2)
    ctx.lineTo(cx + 13.5 * u, headY - 5 * u)
    ctx.quadraticCurveTo(cx, headY - 12 * u, cx - 13.5 * u, headY - 5 * u)
  }
  ctx.closePath()
  ctx.fill()

  // Eyebrows (raise slightly while speaking).
  const brow = s.speaking ? s.level * 0.8 * u : 0
  ctx.strokeStyle = look.hair
  ctx.lineWidth = u * 0.9
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(cx - 8 * u, headY - 5.5 * u - brow)
  ctx.quadraticCurveTo(cx - 5.5 * u, headY - 7 * u - brow, cx - 3 * u, headY - 5.8 * u - brow)
  ctx.moveTo(cx + 3 * u, headY - 5.8 * u - brow)
  ctx.quadraticCurveTo(cx + 5.5 * u, headY - 7 * u - brow, cx + 8 * u, headY - 5.5 * u - brow)
  ctx.stroke()

  // Eyes (blink, and glance up a little while "thinking").
  const blink = blinkAmount(s.time)
  const look_up = s.thinking ? -0.8 * u : 0
  for (const side of [-1, 1]) {
    const ex = cx + side * 5.5 * u
    const ey = headY - 2 * u
    ctx.fillStyle = '#ffffff'
    ctx.beginPath()
    ctx.ellipse(ex, ey, 2.4 * u, 1.6 * u * (1 - blink), 0, 0, Math.PI * 2)
    ctx.fill()
    if (blink < 0.7) {
      ctx.fillStyle = '#2b1d14'
      ctx.beginPath()
      ctx.arc(ex, ey + look_up, 1.15 * u, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = 'rgba(255,255,255,0.8)'
      ctx.beginPath()
      ctx.arc(ex + 0.4 * u, ey - 0.4 * u + look_up, 0.35 * u, 0, Math.PI * 2)
      ctx.fill()
    }
  }

  // Nose.
  ctx.strokeStyle = look.skinShade
  ctx.lineWidth = u * 0.6
  ctx.beginPath()
  ctx.moveTo(cx, headY - 1 * u)
  ctx.quadraticCurveTo(cx - 1.6 * u, headY + 4 * u, cx, headY + 4.6 * u)
  ctx.stroke()

  // Mouth: a smile when quiet, opening with the voice level.
  const open = s.speaking ? Math.max(0.08, s.level) : 0
  ctx.fillStyle = '#7a2e2e'
  ctx.strokeStyle = '#8c3b3b'
  if (open > 0.05) {
    ctx.beginPath()
    ctx.ellipse(cx, headY + 8.3 * u, 3.6 * u, 0.5 * u + open * 2.6 * u, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = '#f5f5f5'
    ctx.fillRect(cx - 2.4 * u, headY + 8.3 * u - (0.5 * u + open * 2.6 * u), 4.8 * u, 0.9 * u)
  } else {
    ctx.lineWidth = u * 0.7
    ctx.beginPath()
    ctx.moveTo(cx - 3.6 * u, headY + 7.8 * u)
    ctx.quadraticCurveTo(cx, headY + 10 * u, cx + 3.6 * u, headY + 7.8 * u)
    ctx.stroke()
  }
  ctx.restore()

  // "Thinking" dots above the head.
  if (s.thinking) {
    for (let i = 0; i < 3; i++) {
      const a = 0.3 + 0.7 * Math.max(0, Math.sin(s.time / 220 - i * 0.7))
      ctx.fillStyle = `rgba(60,70,90,${a})`
      ctx.beginPath()
      ctx.arc(cx - 4 * u + i * 4 * u, headY - 24 * u, 1.2 * u, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}
