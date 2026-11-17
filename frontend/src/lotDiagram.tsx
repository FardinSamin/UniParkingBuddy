import { buildStalls, type DiagramLayout } from './diagramLayout.ts'

interface Props {
  layout: DiagramLayout
  statuses: { id: number; occupied: boolean }[]
}

type Point = [number, number]

function centroid(points: Point[]): Point {
  const sx = points.reduce((sum, p) => sum + p[0], 0)
  const sy = points.reduce((sum, p) => sum + p[1], 0)
  return [sx / points.length, sy / points.length]
}

function shrink(points: Point[], amount: number): Point[] {
  const [cx, cy] = centroid(points)
  return points.map(([x, y]): Point => {
    const dx = cx - x
    const dy = cy - y
    const distance = Math.hypot(dx, dy) || 1
    const k = Math.min(amount / distance, 0.4)
    return [x + dx * k, y + dy * k]
  })
}

function LotDiagram({ layout, statuses }: Props) {
  const occupiedById = new Map<number, boolean>(
    statuses.map((s): [number, boolean] => [s.id, s.occupied]),
  )
  const inset = layout.width / 250
  const strokeWidth = Math.max(1.2, layout.width / 450)
  const fontSize = layout.labelSize ?? Math.round(layout.width / 56)
  const stalls = buildStalls(layout)
  const mappedIds = new Set(stalls.map((stall) => stall.id))
  // Preserve statuses for configured spaces whose positions have not yet
  // been independently drawn/verified on this schematic image.
  const unmapped = statuses.filter((space) => !mappedIds.has(space.id))
    .sort((a, b) => a.id - b.id)

  return (
    <>
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

      {stalls.map((stall) => {
        const occupied = occupiedById.get(stall.id)
        const known = occupied !== undefined
        const fill = !known ? 'none' : occupied ? 'rgba(192,57,43,0.6)' : 'rgba(26,138,74,0.6)'
        const stroke = !known ? '#FFFFFF' : occupied ? '#C0392B' : '#1A8A4A'
        const inner = shrink(stall.points, inset)
        const [cx, cy] = centroid(stall.points)

        return (
          <g key={stall.id} className={`diagram-stall ${!known ? 'unknown' : occupied ? 'occupied' : 'open'}`} data-space-id={stall.id} data-status={!known ? 'UNKNOWN' : occupied ? 'OCCUPIED' : 'AVAILABLE'}>
            <title>{`Space ${stall.id}: ${!known ? 'status unavailable' : occupied ? 'Occupied' : 'Open'}`}</title>
            <polygon
              points={inner.map(([x, y]) => `${x},${y}`).join(' ')}
              fill={fill}
              stroke={stroke}
              strokeWidth={strokeWidth}
              strokeLinejoin="round"
              strokeDasharray={known ? undefined : `${strokeWidth * 3} ${strokeWidth * 2.4}`}
            />
            <text
              x={cx}
              y={cy}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={fontSize}
              fontWeight={700}
              fill="#FFFFFF"
              stroke="rgba(0,0,0,0.45)"
              strokeWidth={fontSize / 5}
              paintOrder="stroke"
            >
              {stall.id}
            </text>
          </g>
        )
      })}
    </svg>
    {unmapped.length > 0 && (
      <section className="unmapped-spaces" aria-label="Configured spaces not drawn on the diagram">
        <p>Some configured spaces have no verified position on this schematic. Their current states are shown here instead of placing them inaccurately.</p>
        <ul className="unmapped-space-list">
          {unmapped.map((space) => (
            <li key={space.id} className={`unmapped-space ${space.occupied ? 'occupied' : 'open'}`} data-space-id={space.id} data-status={space.occupied ? 'OCCUPIED' : 'AVAILABLE'}>
              Space {space.id}: {space.occupied ? 'Occupied' : 'Open'}
            </li>
          ))}
        </ul>
      </section>
    )}
    </>
  )
}

export default LotDiagram