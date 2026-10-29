import { buildStalls, type DiagramLayout } from './diagramLayout.ts'

interface Props {
    layout: DiagramLayout
    statuses: { id: number; occupied: boolean } []

}

const INSET = 3

function lotDiagram({ layout, statuses }: Props) {
    const occupiedById = new Map<number, boolean>(
        statuses.map((s): [number, boolean] => [s.id, s.occupied]),
  )
  const fontSize = Math.round(layout.width / 56)

  return (
    <svg
      viewBox={`0 0 ${layout.width} ${layout.height}`}
      className="lot-diagram"
      role="img"
      aria-label="Parking lot diagram"
    >
      {layout.image ? (
        <image href={layout.image} width={layout.width} height={layout.height} />
      ) : (
        <rect width={layout.width} height={layout.height} fill="#6E6A62" />
      )}

      {buildStalls(layout).map((stall) => {
        const occupied = occupiedById.get(stall.id)
        const known = occupied !== undefined
        const fill = !known ? 'none' : occupied ? 'rgba(192,57,43,0.6)' : 'rgba(26,138,74,0.6)'
        const stroke = !known ? '#FFFFFF' : occupied ? '#C0392B' : '#1A8A4A'
        const w = stall.width - 2 * INSET
        const h = stall.height - 2 * INSET

        return (
          <g key={stall.id}>
            <rect
              x={stall.x + INSET}
              y={stall.y + INSET}
              width={w}
              height={h}
              rx={5}
              fill={fill}
              stroke={stroke}
              strokeWidth={2.5}
              strokeDasharray={known ? undefined : '8 6'}
            />
            <text
              x={stall.x + INSET + w / 2}
              y={stall.y + INSET + h / 2}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={fontSize}
              fontWeight={700}
              fill="#FFFFFF"
              stroke="rgba(0,0,0,0.45)"
              strokeWidth={3}
              paintOrder="stroke"
            >
              {stall.id}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default lotDiagram
   