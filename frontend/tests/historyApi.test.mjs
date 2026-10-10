import test from 'node:test'
import assert from 'node:assert/strict'
import { fetchTrends, fetchSpaceHistory } from '../src/historyApi.ts'

function reply(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status, headers: { 'Content-Type': 'application/json' },
  })
}

async function withFetch(handler, run) {
  const old = globalThis.fetch
  globalThis.fetch = handler
  try {
    await run()
  } finally {
    globalThis.fetch = old
  }
}

const goodTrends = {
  lot_id: 'lot1',
  days: 7,
  timezone: 'UTC',
  space_ids: ['1', '7'],
  has_history: true,
  hourly: [
    { hour_utc: 13, observations: 4, occupied_observations: 2, occupied_percent: 50 },
  ],
  basis: 'observed occupancy samples; not parked duration or prediction',
}

test('historical trends load only for the selected lot and window', async () => {
  await withFetch(
    async (url) => {
      assert.equal(url, 'http://localhost:5000/api/trends/lot1?days=7')
      return reply(goodTrends)
    },
    async () => {
      const data = await fetchTrends('lot1')
      assert.equal(data.hourly[0].occupied_percent, 50)
      assert.equal(data.space_ids.length, 2)
    },
  )
})

test('empty history is valid and distinct from a zero percent observation', async () => {
  await withFetch(
    async () => reply({ ...goodTrends, has_history: false, hourly: [] }),
    async () => {
      const data = await fetchTrends('lot1')
      assert.equal(data.has_history, false)
      assert.deepEqual(data.hourly, [])
    },
  )
})

test('observed zero occupancy must include a nonzero sample count', async () => {
  await withFetch(
    async () => reply({ ...goodTrends, hourly: [
      { hour_utc: 13, observations: 2, occupied_observations: 0, occupied_percent: 0 },
    ] }),
    async () => {
      const data = await fetchTrends('lot1')
      assert.equal(data.hourly[0].occupied_percent, 0)
      assert.equal(data.hourly[0].observations, 2)
    },
  )
})

test('invalid negative or impossible observed occupancy samples are rejected', async () => {
  const badHours = [
    { hour_utc: 25, observations: 2, occupied_observations: 1, occupied_percent: 50 },
    { hour_utc: 2, observations: 0, occupied_observations: 0, occupied_percent: 0 },
    { hour_utc: 2, observations: 2, occupied_observations: 3, occupied_percent: 150 },
    { hour_utc: 2, observations: 2, occupied_observations: 1, occupied_percent: NaN },
  ]
  for (const row of badHours) {
    await withFetch(
      async () => reply({ ...goodTrends, hourly: [row] }),
      async () => assert.rejects(fetchTrends('lot1')),
    )
  }
})

test('duplicate hour buckets and incompatible lot responses are rejected', async () => {
  await withFetch(
    async () => reply({ ...goodTrends, hourly: [
      goodTrends.hourly[0], goodTrends.hourly[0],
    ] }),
    async () => assert.rejects(fetchTrends('lot1')),
  )
  await withFetch(
    async () => reply({ ...goodTrends, lot_id: 'lot2' }),
    async () => assert.rejects(fetchTrends('lot1')),
  )
})

test('failed database response is rejected rather than treated as no history', async () => {
  await withFetch(
    async () => reply({ error: 'Historical data is not configured' }, 503),
    async () => assert.rejects(fetchTrends('lot1')),
  )
})

test('invalid day windows are rejected before fetching', async () => {
  await withFetch(
    async () => { throw new Error('should not request data') },
    async () => {
      await assert.rejects(fetchTrends('lot1', 0))
      await assert.rejects(fetchTrends('lot1', 32))
    },
  )
})

test('space history preserves two domain states and timestamp values', async () => {
  await withFetch(
    async (url) => {
      assert.equal(url, 'http://localhost:5000/api/history/lot1/7')
      return reply({
        lot_id: 'lot1',
        space_id: '7',
        has_history: true,
        records: [
          { status: 'OCCUPIED', observed_at: '2026-10-10T13:00:00+00:00' },
          { status: 'AVAILABLE', observed_at: '2026-10-10T12:00:00+00:00' },
        ],
      })
    },
    async () => {
      const data = await fetchSpaceHistory('lot1', '7')
      assert.equal(data.records.length, 2)
      assert.equal(data.records[0].status, 'OCCUPIED')
    },
  )
})

test('unknown domain status or impossible timestamp is rejected', async () => {
  for (const record of [
    { status: 'UNKNOWN', observed_at: '2026-10-10T13:00:00+00:00' },
    { status: 'AVAILABLE', observed_at: 'not-a-date' },
  ]) {
    await withFetch(
      async () => reply({ lot_id: 'lot1', space_id: '7', has_history: true, records: [record] }),
      async () => assert.rejects(fetchSpaceHistory('lot1', '7')),
    )
  }
})

test('empty space history requires has_history=false', async () => {
  await withFetch(
    async () => reply({ lot_id: 'lot1', space_id: '7', has_history: false, records: [] }),
    async () => assert.equal((await fetchSpaceHistory('lot1', '7')).has_history, false),
  )
  await withFetch(
    async () => reply({ lot_id: 'lot1', space_id: '7', has_history: true, records: [] }),
    async () => assert.rejects(fetchSpaceHistory('lot1', '7')),
  )
})

test('historical percentage must agree with observation counts', async () => {
  await withFetch(
    async () => reply({ ...goodTrends, hourly: [
      { hour_utc: 13, observations: 4, occupied_observations: 1, occupied_percent: 90 },
    ] }),
    async () => assert.rejects(fetchTrends('lot1')),
  )
})
