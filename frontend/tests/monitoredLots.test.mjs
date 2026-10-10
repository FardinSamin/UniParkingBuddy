import test from 'node:test'
import assert from 'node:assert/strict'

import { fetchMonitoredLots, validateMonitoredLots } from '../src/monitoredLots.ts'
import { getApiJson } from '../src/apiClient.ts'

const lot1 = {
  lot_id: 'lot1',
  display_label: 'Lot 1',
  camera: 'camera_1',
  space_ids: [1, 7],
  total_spaces: 2,
  has_current_data: true,
  available_spaces: 1,
  occupied_spaces: 1,
}

const lot2 = {
  lot_id: 'lot2',
  display_label: 'Lot 2',
  camera: 'camera_2',
  space_ids: [3],
  total_spaces: 1,
  has_current_data: false,
  available_spaces: null,
  occupied_spaces: null,
}

function response(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function withFetch(mock, fn) {
  const old = globalThis.fetch
  globalThis.fetch = mock
  try {
    await fn()
  } finally {
    globalThis.fetch = old
  }
}

test('configured lots load using same-origin /api/lots and retain actual IDs', async () => {
  await withFetch(
    async (url) => {
      assert.equal(url, '/api/lots')
      return response({ lots: [lot1, lot2] })
    },
    async () => {
      const data = await fetchMonitoredLots()
      assert.deepEqual(data.map((lot) => lot.lot_id), ['lot1', 'lot2'])
      assert.deepEqual(data[0].space_ids, [1, 7])
      assert.equal(data[1].available_spaces, null)
    },
  )
})

test('empty active monitoring list is valid, no fabricated Lot 3', () => {
  assert.deepEqual(validateMonitoredLots({ lots: [] }), [])
})

test('a full monitored lot is valid only with real current data', () => {
  const result = validateMonitoredLots({
    lots: [{ ...lot1, available_spaces: 0, occupied_spaces: 2 }],
  })
  assert.equal(result[0].has_current_data, true)
  assert.equal(result[0].available_spaces, 0)
})

test('missing status has nullable counts, not fabricated zero availability', () => {
  const result = validateMonitoredLots({ lots: [lot2] })
  assert.equal(result[0].has_current_data, false)
  assert.equal(result[0].available_spaces, null)
  assert.equal(result[0].occupied_spaces, null)
})

test('server failures are unavailable and never converted to empty active lists', async () => {
  await withFetch(
    async () => response({ error: 'backend failed' }, 503),
    async () => assert.rejects(fetchMonitoredLots()),
  )
})

test('malformed or absent monitored-lots list is rejected', () => {
  for (const raw of [null, [], {}, { lots: null }, { lots: [null] }]) {
    assert.throws(() => validateMonitoredLots(raw))
  }
})

test('inconsistent, negative and fractional counts are rejected', () => {
  const bad = [
    { available_spaces: 2, occupied_spaces: 2 },
    { available_spaces: -1, occupied_spaces: 3 },
    { available_spaces: 0.5, occupied_spaces: 1.5 },
    { total_spaces: 3 },
    { has_current_data: true, available_spaces: null, occupied_spaces: null },
  ]
  for (const patch of bad) {
    assert.throws(() => validateMonitoredLots({ lots: [{ ...lot1, ...patch }] }))
  }
})

test('unknown state must not contain numeric zero counts', () => {
  assert.throws(() => validateMonitoredLots({
    lots: [{ ...lot2, available_spaces: 0, occupied_spaces: 0 }],
  }))
})

test('duplicate space IDs and unsupported space ID values are rejected', () => {
  for (const ids of [[1, 1], [0, 2], [-1, 2], [1.5, 2], [true, 2]]) {
    assert.throws(() => validateMonitoredLots({
      lots: [{ ...lot1, space_ids: ids }],
    }))
  }
})

test('duplicate lot IDs or camera mappings are rejected', () => {
  assert.throws(() => validateMonitoredLots({
    lots: [lot1, { ...lot2, lot_id: 'lot1' }],
  }))
  assert.throws(() => validateMonitoredLots({
    lots: [lot1, { ...lot2, camera: 'camera_1' }],
  }))
})

test('invalid labels, cameras, or active-empty monitoring are rejected', () => {
  for (const patch of [
    { display_label: '' },
    { camera: '' },
    { lot_id: '' },
    { total_spaces: 0, space_ids: [], available_spaces: 0, occupied_spaces: 0 },
  ]) {
    assert.throws(() => validateMonitoredLots({
      lots: [{ ...lot1, ...patch }],
    }))
  }
})

test('fetch errors and paths outside /api are rejected', async () => {
  await withFetch(
    async () => { throw new Error('network down') },
    async () => assert.rejects(fetchMonitoredLots()),
  )
  await assert.rejects(getApiJson('http://localhost:5000/api/lots'))
  await assert.rejects(getApiJson('/anything'))
})
