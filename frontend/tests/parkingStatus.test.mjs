import test from 'node:test'
import assert from 'node:assert/strict'
import { fetchParkingStatus } from '../src/parkingStatus.ts'

function reply(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function withMockFetch(mock, run) {
  const originalFetch = globalThis.fetch
  globalThis.fetch = mock
  try {
    await run()
  } finally {
    globalThis.fetch = originalFetch
  }
}

test('valid current occupancy is returned, including a genuinely full lot', async () => {
  await withMockFetch(
    async (url) => {
      assert.equal(url, 'http://localhost:5000/api/status/camera_1')
      return reply({ cars_detected: 2, parking_spaces: [
        { id: 1, occupied: true },
        { id: 2, occupied: true },
      ] })
    },
    async () => {
      const data = await fetchParkingStatus('camera_1')
      assert.equal(data.parking_spaces.length, 2)
      assert.equal(data.parking_spaces.filter((space) => !space.occupied).length, 0)
    },
  )
})

test('no configured spaces is unavailable, not a full lot', async () => {
  await withMockFetch(
    async () => reply({ cars_detected: 0, parking_spaces: [] }),
    async () => assert.rejects(fetchParkingStatus('camera_1')),
  )
})

test('server not-ready response is unavailable', async () => {
  await withMockFetch(
    async () => reply({ error: 'Parking status is not ready' }, 503),
    async () => assert.rejects(fetchParkingStatus('camera_1')),
  )
})

test('malformed occupancy data is rejected', async () => {
  await withMockFetch(
    async () => reply({ cars_detected: 1, parking_spaces: [{ id: 1, occupied: 'yes' }] }),
    async () => assert.rejects(fetchParkingStatus('camera_1')),
  )
})

test('duplicate parking space IDs are rejected', async () => {
  await withMockFetch(
    async () => reply({ cars_detected: 1, parking_spaces: [
      { id: 1, occupied: true },
      { id: 1, occupied: false },
    ] }),
    async () => assert.rejects(fetchParkingStatus('camera_1')),
  )
})

test('zero vehicle detections with configured spaces is valid', async () => {
  await withMockFetch(
    async () => reply({ cars_detected: 0, parking_spaces: [
      { id: 1, occupied: false },
      { id: 2, occupied: false },
    ] }),
    async () => {
      const data = await fetchParkingStatus('camera_2')
      assert.equal(data.cars_detected, 0)
      assert.equal(data.parking_spaces.length, 2)
    },
  )
})

test('network failures are unavailable', async () => {
  await withMockFetch(
    async () => { throw new Error('Network is down') },
    async () => assert.rejects(fetchParkingStatus('camera_1')),
  )
})

test('valid inside/outside breakdown is preserved', async () => {
  await withMockFetch(
    async () => reply({
      cars_detected: 3,
      vehicles_in_spaces: 1,
      vehicles_outside_spaces: 2,
      parking_spaces: [{ id: 1, occupied: true }, { id: 2, occupied: false }],
    }),
    async () => {
      const data = await fetchParkingStatus('camera_1')
      assert.equal(data.vehicles_in_spaces, 1)
      assert.equal(data.vehicles_outside_spaces, 2)
    },
  )
})

test('vehicle breakdown is optional for older backend responses', async () => {
  await withMockFetch(
    async () => reply({
      cars_detected: 1,
      parking_spaces: [{ id: 1, occupied: true }],
    }),
    async () => {
      const data = await fetchParkingStatus('camera_1')
      assert.equal(data.vehicles_outside_spaces, undefined)
    },
  )
})

test('inconsistent vehicle breakdown is rejected', async () => {
  await withMockFetch(
    async () => reply({
      cars_detected: 2,
      vehicles_in_spaces: 1,
      vehicles_outside_spaces: 2,
      parking_spaces: [{ id: 1, occupied: true }],
    }),
    async () => assert.rejects(fetchParkingStatus('camera_1')),
  )
})

test('partial breakdown without both values is rejected', async () => {
  await withMockFetch(
    async () => reply({
      cars_detected: 2,
      vehicles_outside_spaces: 1,
      parking_spaces: [{ id: 1, occupied: true }],
    }),
    async () => assert.rejects(fetchParkingStatus('camera_1')),
  )
})
