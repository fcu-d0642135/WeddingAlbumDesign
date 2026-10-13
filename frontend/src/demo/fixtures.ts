/**
 * 展示版的假資料，內容照搬後端 `flask seed`（backend/app/seed.py），兩邊看起來一樣。
 * 照片是漸層色塊，跟 seed 產生的測試照片同一組顏色。
 */
import type { PhotoTag } from '@/types/album'

/** (暱稱, 與新人的關係) */
export const GUESTS: [string, string | null][] = [
  ['小慧', '新娘的大學同學'],
  ['阿凱', '新郎的大學室友'],
  ['婷婷', null],
  ['志明', null],
  ['美玲阿姨', '新娘的阿姨'],
  ['建宏', null],
  ['佳穎', null],
  ['俊豪', null],
]

/** (上傳者在 GUESTS 的位置, 寬, 高, 分類)。順序就是上傳的先後 */
export const PHOTOS: [number, number, number, PhotoTag][] = [
  [0, 3, 4, 'welcome'],
  [1, 4, 5, 'welcome'],
  [2, 1, 1, 'ceremony'],
  [3, 4, 3, 'ceremony'],
  [4, 3, 4, 'ceremony'],
  [2, 3, 4, 'ceremony'],
  [5, 4, 5, 'banquet'],
  [6, 1, 1, 'banquet'],
  [7, 3, 4, 'banquet'],
  [2, 4, 3, 'banquet'],
  [0, 4, 5, 'banquet'],
  [1, 3, 2, 'banquet'],
]

/** (作者在 GUESTS 的位置, 祝福, 掛在第幾張照片上或 null)。照片必須是作者自己上傳的 */
export const BLESSINGS: [number, string, number | null][] = [
  [
    1,
    '俊鴻是我大學最好的兄弟，一路看著他追到鈺婷。今天看到你們穿上禮服，眼淚差點掉下來。祝你們白頭偕老！',
    1,
  ],
  [4, '從小看著婷婷長大，今天看到她當新娘真的好美。願你們的婚姻甜甜蜜蜜，早生貴子。', null],
  [3, '恭喜恭喜！', null],
  [6, '兩個人在一起的樣子真好看。 ♥', null],
]

/** (按讚的人在 GUESTS 的位置, 第幾張照片) */
export const LIKES: [number, number][] = [
  [0, 1],
  [2, 1],
  [3, 1],
  [5, 1],
  [0, 2],
  [4, 6],
  [6, 6],
]

/** 婚紗集 (寬, 高) */
export const WEDDING: [number, number][] = [
  [3, 2],
  [3, 4],
  [1, 1],
  [1, 1],
  [3, 2],
  [3, 4],
  [1, 1],
  [1, 1],
]

/** 跟前端 PhotoTile 的佔位漸層、後端 seed 同一組顏色 */
const GRADIENTS: [string, string][] = [
  ['#E8D4C8', '#C9A48E'],
  ['#D4B8A8', '#A88876'],
  ['#EAD9C5', '#C2A179'],
  ['#D9C2B0', '#A88562'],
  ['#E5D0BE', '#B8967A'],
  ['#DBC5B2', '#9C7E68'],
  ['#EFDFC9', '#C49E7C'],
  ['#E0CAB8', '#A8836A'],
  ['#E8D8C5', '#BC9778'],
  ['#D6BCA9', '#9D7B62'],
]

const LONG_EDGE = 1600

export function sizeOf(wRatio: number, hRatio: number) {
  const scale = LONG_EDGE / Math.max(wRatio, hRatio)
  return { width: Math.round(wRatio * scale), height: Math.round(hRatio * scale) }
}

/** 左上淺、右下深的斜向漸層，做成 SVG data URL，不必另外放圖檔 */
export function gradientImage(width: number, height: number, index: number) {
  const [from, to] = GRADIENTS[index % GRADIENTS.length]!
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">` +
    `<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">` +
    `<stop offset="0" stop-color="${from}"/><stop offset="1" stop-color="${to}"/>` +
    `</linearGradient></defs><rect width="100%" height="100%" fill="url(#g)"/></svg>`
  return 'data:image/svg+xml,' + encodeURIComponent(svg)
}
