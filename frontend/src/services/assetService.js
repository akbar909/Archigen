import { apiClient } from './apiClient'

let catalogPromise = null
let fetchedAt = 0

export async function fetchUploadedAssetCatalog({ refresh = false } = {}) {
  if (!catalogPromise || refresh || Date.now() - fetchedAt > 15 * 60 * 1000) {
    fetchedAt = Date.now()
    catalogPromise = apiClient.get('/assets/catalog')
      .then(({ data }) => ({ ...data, assets: (data?.assets || []).map((asset) =>
        (asset.asset_id || asset.id)?.toLowerCase() === 'arched_window_01'
          ? { ...asset, model_path: '/models/arched_window_01.glb', canonical_yaw_offset_deg: 0, canonical_pitch_offset_deg: 0 }
          : asset) }))
      .catch((error) => {
        catalogPromise = null
        throw error
      })
  }
  return catalogPromise
}

export async function refreshUploadedAsset(s3Key) {
  if (!s3Key) return null
  const data = await fetchUploadedAssetCatalog({ refresh: true })
  return (data?.assets || []).find((asset) => asset.s3_key === s3Key || asset.alias_s3_keys?.includes(s3Key)) || null
}

