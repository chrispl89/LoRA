'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Person, Photo, PreprocessRun } from '@/types'
import PhotoThumbnail from './PhotoThumbnail'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function PersonDetail() {
  const params = useParams()
  const router = useRouter()
  const personId = parseInt(params.id as string)

  const [person, setPerson] = useState<Person | null>(null)
  const [photos, setPhotos] = useState<Photo[]>([])
  const [preprocessRun, setPreprocessRun] = useState<PreprocessRun | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [preprocessing, setPreprocessing] = useState(false)
  const [deletingPhotoId, setDeletingPhotoId] = useState<number | null>(null)

  useEffect(() => {
    fetchData()
  }, [personId])

  const fetchData = async () => {
    try {
      const personRes = await fetch(`${API_URL}/v1/persons/${personId}`)
      if (!personRes.ok) throw new Error('Failed to fetch person')
      const personData = await personRes.json()
      setPerson(personData)

      // Fetch photos
      try {
        const photosRes = await fetch(`${API_URL}/v1/persons/${personId}/photos`)
        if (photosRes.ok) {
          const photosData = await photosRes.json()
          setPhotos(photosData)
        }
      } catch (err) {
        console.error('Failed to fetch photos:', err)
      }

      // Fetch latest preprocess run
      try {
        const preRes = await fetch(`${API_URL}/v1/persons/${personId}/preprocess/latest`)
        if (preRes.ok) {
          const preData = await preRes.json()
          setPreprocessRun(preData)
        }
      } catch (err) {
        console.error('Failed to fetch preprocess run:', err)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length === 0) return

    setUploading(true)
    setError(null)

    try {
      // Upload sequentially (simpler + avoids overload)
      for (const file of files) {
        // Get presigned URL
        const presignRes = await fetch(
          `${API_URL}/v1/persons/${personId}/uploads/presign`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              filename: file.name,
              content_type: file.type,
              size_bytes: file.size,
            }),
          }
        )

        if (!presignRes.ok) {
          const errorData = await presignRes.json().catch(() => ({ detail: 'Failed to get upload URL' }))
          throw new Error(errorData.detail || 'Failed to get upload URL')
        }
        const { url, key } = await presignRes.json()

        // Upload to S3
        const uploadRes = await fetch(url, {
          method: 'PUT',
          body: file,
          headers: { 'Content-Type': file.type },
        })

        if (!uploadRes.ok) {
          throw new Error(`Upload failed: ${uploadRes.status} ${uploadRes.statusText}`)
        }

        // Complete registration
        const completeRes = await fetch(`${API_URL}/v1/persons/${personId}/photos/complete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            key,
            content_type: file.type,
            size_bytes: file.size,
          }),
        })

        if (!completeRes.ok) {
          const errorData = await completeRes.json().catch(() => ({ detail: 'Failed to register photo' }))
          throw new Error(errorData.detail || 'Failed to register photo')
        }
      }

      // Reset file input
      e.target.value = ''
      
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handlePreprocess = async () => {
    try {
      setPreprocessing(true)
      setError(null)
      const res = await fetch(`${API_URL}/v1/persons/${personId}/preprocess`, {
        method: 'POST',
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Failed to start preprocessing' }))
        throw new Error(data.detail || 'Failed to start preprocessing')
      }
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preprocess failed')
    } finally {
      setPreprocessing(false)
    }
  }

  const handleDeletePhoto = async (photoId: number) => {
    try {
      setDeletingPhotoId(photoId)
      setError(null)
      const res = await fetch(`${API_URL}/v1/persons/${personId}/photos/${photoId}`, { method: 'DELETE' })
      if (!res.ok) {
        const data = await res.json().catch(() => ({ detail: 'Failed to delete photo' }))
        throw new Error(data.detail || 'Failed to delete photo')
      }
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setDeletingPhotoId(null)
    }
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error) return <div className="error">Error: {error}</div>
  if (!person) return <div>Person not found</div>

  const uploadedCount = photos.filter((p) => p.status === 'uploaded').length
  const remainingSlots = Math.max(0, 30 - photos.length)

  return (
    <div className="container">
      <Link href="/">← Back to Home</Link>
      <h1>{person.name}</h1>

      <div className="card">
        <h2>Profile</h2>
        <p>Consent: {person.consent_confirmed ? '✓' : '✗'}</p>
        <p>Adult: {person.subject_is_adult ? '✓' : '✗'}</p>
      </div>

      <div className="card">
        <h2>Photos ({photos.length})</h2>
        <div style={{ marginBottom: '15px' }}>
          <label style={{ display: 'block', marginBottom: '10px', fontWeight: 500 }}>
            Upload Photo
          </label>
          <div style={{ marginBottom: '8px', color: '#666' }}>
            Remaining slots: {remainingSlots} / 30
          </div>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={handleFileUpload}
            disabled={uploading || remainingSlots === 0}
            style={{ 
              padding: '8px',
              border: '1px solid #ddd',
              borderRadius: '4px',
              width: '100%',
              maxWidth: '400px',
              cursor: uploading ? 'not-allowed' : 'pointer'
            }}
          />
          {uploading && (
            <div style={{ marginTop: '10px', color: '#666' }}>
              <span>Uploading...</span>
            </div>
          )}
          {error && (
            <div style={{ marginTop: '10px', color: '#dc3545', fontSize: '14px' }}>
              {error}
            </div>
          )}
        </div>

        {photos.length > 0 && (
          <div className="photo-grid">
            {photos.map((photo) => (
              <div key={photo.id} className="photo-item">
                <PhotoThumbnail personId={personId} photoId={photo.id} />
                <button
                  onClick={() => handleDeletePhoto(photo.id)}
                  disabled={deletingPhotoId === photo.id}
                  title="Delete photo"
                  style={{
                    position: 'absolute',
                    top: '6px',
                    right: '6px',
                    background: 'rgba(0,0,0,0.6)',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    padding: '6px 8px',
                    cursor: 'pointer',
                    fontSize: '12px',
                  }}
                >
                  {deletingPhotoId === photo.id ? '...' : 'Delete'}
                </button>
                <div style={{ position: 'absolute', bottom: '5px', left: '5px' }}>
                  <span className={`status-badge status-${photo.status}`}>
                    {photo.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Preprocessing</h2>
        <p style={{ color: '#666', marginBottom: '10px' }}>
          Preprocessing converts uploaded photos into a processed dataset (dedupe + resize) used for training.
        </p>
        <p style={{ color: '#666', marginBottom: '10px' }}>
          Uploaded: {uploadedCount} / Total: {photos.length}
        </p>
        <button
          onClick={handlePreprocess}
          className="btn btn-primary"
          disabled={preprocessing || uploadedCount < 3}
        >
          {preprocessing ? 'Starting...' : 'Start Preprocessing'}
        </button>
        {preprocessRun && (
          <div style={{ marginTop: '15px' }}>
            <p>Status: <span className={`status-badge status-${preprocessRun.status}`}>
              {preprocessRun.status}
            </span></p>
            {preprocessRun.images_accepted > 0 && (
              <p>Accepted: {preprocessRun.images_accepted}</p>
            )}
            {preprocessRun.images_duplicates > 0 && (
              <p>Duplicates: {preprocessRun.images_duplicates}</p>
            )}
            {preprocessRun.images_rejected > 0 && (
              <p>Rejected: {preprocessRun.images_rejected}</p>
            )}
            {preprocessRun.error_message && (
              <p style={{ color: '#dc3545' }}>Error: {preprocessRun.error_message}</p>
            )}
          </div>
        )}
      </div>

      <div className="card">
        <h2>Models</h2>
        <Link href={`/persons/${personId}/models`} className="btn btn-primary">
          View Models
        </Link>
      </div>
    </div>
  )
}
