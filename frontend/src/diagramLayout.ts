export interface DiagramColumn {
    name: string
    x0: number
    x1: number
    lines: number[]
}

export interface DiagramLayout {
    image?: string
    width: number
    height: number
    columns: DiagramColumn[]

}

export interface Stall {
    id: number
    column: string
    x: number
    y: number
    width: number
    height: number 
}

export function buildStalls(layout: DiagramLayout): Stall[] {
    const stalls: Stall[] = []
    let id=1 
    for (const column of layout.columns) {
        for (let row = 0; row < column.lines.length - 1; row++) {
            stalls.push({
                id,
                column: column.name,
                x: column.x0,
                y: column.lines[row],
                width: column.x1 - column.x0,
                height: column.lines[row + 1] - column.lines[row],
            })
            id++
            }
        }
        return stalls
    }
