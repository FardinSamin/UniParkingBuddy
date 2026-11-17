import test from 'node:test'
import assert from 'node:assert/strict'
import {
  defaultCampusTarget, fetchForecast, validateForecast,
} from '../src/forecastApi.ts'

const demo = {
  requested_at: '2026-11-11T14:00:00-05:00',
  timezone: 'America/New_York',
  mode: 'demo',
  source: 'synthetic_demo',
  model: 'illustrative_schedule_v1',
  basis: 'Illustrative scheduling only; not real campus data',
  historical_enabled: false,
  lots: [
    {
      lot_id: 'lot1', display_label: 'Lot 1',
      total_spaces: 10, status: 'illustrative',
      estimated_available: 6, estimated_occupied: 4, estimated_open_percent: 60,
      historical_days: 0, historical_snapshots: 0,
    },
  ],
}

function reply(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status, headers: { 'Content-Type': 'application/json' },
  })
}

async function withFetch(fn, callback) {
  const original = globalThis.fetch
  globalThis.fetch = fn
  try {
    await callback()
  } finally {
    globalThis.fetch = original
  }
}

test('uses campus calendar rather than client UTC or device timezone', () => {
  assert.equal(
    defaultCampusTarget(new Date('2026-11-11T02:00:00Z')),
    '2026-11-11T14:00',
  )
  assert.equal(
    defaultCampusTarget(new Date('2027-03-14T03:00:00Z')),
    '2027-03-14T14:00',
  )
})

test('read-only forecast stays same origin and preserves selected campus wall clock', async () => {
  await withFetch(
    async (url) => {
      assert.equal(
        url, '/api/forecast?at=2026-11-11T14%3A00&mode=demo',
      )
      return reply(demo)
    },
    async () => {
      const result = await fetchForecast('2026-11-11T14:00', 'demo')
      assert.equal(result.source, 'synthetic_demo')
      assert.equal(result.lots[0].estimated_available, 6)
    },
  )
})

test('synthetic and trusted-data sources cannot be mislabeled', () => {
  for (const patch of [
    { source: 'verified_history' },
    { mode: 'historical' },
    { model: 'weekday_hour_baseline_v1' },
    { requested_at: 'bad' },
    { timezone: 'UTC' },
    { basis: '' },
  ]) {
    assert.throws(() => validateForecast({ ...demo, ...patch }, 'demo'))
  }
})

test('counts, sample sizes, and percentages must be self-consistent', () => {
  for (const patch of [
    { estimated_available: -1 },
    { estimated_available: 7 },
    { estimated_available: 2.4 },
    { estimated_occupied: 12 },
    { estimated_open_percent: 71 },
    { historical_days: 2 },
    { historical_snapshots: 4 },
    { total_spaces: 0 },
  ]) {
    assert.throws(() => validateForecast({
      ...demo, lots: [{ ...demo.lots[0], ...patch }],
    }, 'demo'))
  }
})

test('duplicate lot IDs and malformed payloads fail closed', () => {
  assert.throws(() => validateForecast({
    ...demo, lots: [demo.lots[0], { ...demo.lots[0] }],
  }, 'demo'))
  for (const value of [null, {}, [], { ...demo, lots: null }]) {
    assert.throws(() => validateForecast(value, 'demo'))
  }
})

test('insufficient historical evidence cannot pretend to have zero open spaces', () => {
  const history = {
    ...demo,
    mode: 'historical',
    source: 'verified_history',
    model: 'weekday_hour_baseline_v1',
    historical_enabled: true,
    lots: [{
      ...demo.lots[0],
      status: 'insufficient_history', estimated_available: null,
      estimated_occupied: null, estimated_open_percent: null,
      historical_days: 1, historical_snapshots: 50,
    }],
  }
  assert.equal(validateForecast(history, 'historical').lots[0].estimated_available, null)
  assert.throws(() => validateForecast({
    ...history,
    lots: [{ ...history.lots[0], estimated_available: 0 }],
  }, 'historical'))
})

test('historical estimate requires three distinct days and valid counts', () => {
  const history = {
    ...demo, mode: 'historical', source: 'verified_history',
    model: 'weekday_hour_baseline_v1',
    historical_enabled: true,
    lots: [{ ...demo.lots[0], status: 'historical_estimate',
      historical_days: 3, historical_snapshots: 12 }],
  }
  assert.equal(validateForecast(history, 'historical').lots[0].historical_days, 3)
  assert.throws(() => validateForecast({
    ...history, lots: [{ ...history.lots[0], historical_days: 2 }],
  }, 'historical'))
})

test('API errors stay unavailable, never fabricated as demo predictions', async () => {
  await withFetch(
    async () => reply({ error: 'The backend is unavailable' }, 503),
    async () => assert.rejects(fetchForecast('2026-11-11T14:00', 'demo')),
  )
})

test('invalid wall-clock input is refused before any network request', async () => {
  await withFetch(
    async () => { throw new Error('Request should not have been sent') },
    async () => {
      await assert.rejects(fetchForecast('yesterday', 'demo'))
      await assert.rejects(fetchForecast('2026-11-11', 'demo'))
      await assert.rejects(fetchForecast('2026-11-11T14:00Z', 'demo'))
    },
  )
})
