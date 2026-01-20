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
      // TODO: Add endpoint for this
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setError(null)

    try {
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

      if (!presignRes.ok) throw new Error('Failed to get upload URL')
      const { url, key } = await presignRes.json()

      // Upload to S3
      const uploadRes = await fetch(url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type },
      })

      if (!uploadRes.ok) throw new Error('Upload failed')

      // Complete registration
      await fetch(`${API_URL}/v1/persons/${personId}/photos/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          key,
          content_type: file.type,
          size_bytes: file.size,
        }),
      })

      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handlePreprocess = async () => {
    try {
      const res = await fetch(`${API_URL}/v1/persons/${personId}/preprocess`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error('Failed to start preprocessing')
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preprocess failed')
    }
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error) return <div className="error">Error: {error}</div>
  if (!person) return <div>Person not found</div>

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
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileUpload}
            disabled={uploading}
          />
          {uploading && <span style={{ marginLeft: '10px' }}>Uploading...</span>}
        </div>

        {photos.length > 0 && (
          <div className="photo-grid">
            {photos.map((photo) => (
              <div key={photo.id} className="photo-item">
                <PhotoThumbnail personId={personId} photoId={photo.id} />
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
        <button
          onClick={handlePreprocess}
          className="btn btn-primary"
          disabled={photos.length < 3}
        >
          Start Preprocessing
        </button>
        {preprocessRun && (
          <div style={{ marginTop: '15px' }}>
            <p>Status: <span className={`status-badge status-${preprocessRun.status}`}>
              {preprocessRun.status}
            </span></p>
            {preprocessRun.images_accepted > 0 && (
              <p>Accepted: {preprocessRun.images_accepted}</p>
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
