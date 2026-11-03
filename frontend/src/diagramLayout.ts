export interface DiagramColumn {
  name: string
  x0: number
  x1: number
  lines: number[]
}

export interface DiagramStall {
  id: number
  group?: string
  points: [number, number][]
}

export interface DiagramLayout {
  image?: string
  labelSize?: number
  width: number
  height: number
  columns?: DiagramColumn[]  
  stalls?: DiagramStall[]    
  mapping?: Record<string, number>
}

export interface Stall {
  id: number
  column: string
  points: [number, number][]
}

export function buildStalls(layout: DiagramLayout): Stall[] {
  const stalls: Stall[] = []

  for (const stall of layout.stalls ?? []) {
    stalls.push({ id: stall.id, column: stall.group ?? '', points: stall.points })
  }

  let id = 1
  for (const column of layout.columns ?? []) {
    for (let row = 0; row < column.lines.length - 1; row++) {
      const top = column.lines[row]
      const bottom = column.lines[row + 1]
      stalls.push({
        id,
        column: column.name,
        points: [
          [column.x0, top],
          [column.x1, top],
          [column.x1, bottom],
          [column.x0, bottom],
        ],
      })
      id++
    }
  }

  return stalls
}