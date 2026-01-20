'use client'

import { useState, useEffect } from 'react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function PhotoThumbnail({ personId, photoId }: { personId: number; photoId: number }) {
  const [url, setUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API_URL}/v1/persons/${personId}/photos/${photoId}/url`)
      .then(res => res.json())
      .then(data => {
        setUrl(data.url)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [personId, photoId])

  if (loading) return <div style={{ padding: '20px', textAlign: 'center' }}>Loading...</div>
  if (!url) return <div style={{ padding: '20px', textAlign: 'center' }}>No image</div>

  return <img src={url} alt={`Photo ${photoId}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
}
