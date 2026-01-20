'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Person } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function CreatePerson() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [consentConfirmed, setConsentConfirmed] = useState(false)
  const [subjectIsAdult, setSubjectIsAdult] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)

    try {
      const response = await fetch(`${API_URL}/v1/persons`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          consent_confirmed: consentConfirmed,
          subject_is_adult: subjectIsAdult,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to create person')
      }

      const person: Person = await response.json()
      router.push(`/persons/${person.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1>Create Person Profile</h1>
      <div className="card">
        <form onSubmit={handleSubmit}>
          {error && <div className="error">{error}</div>}
          
          <div className="form-group">
            <label>Name *</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={consentConfirmed}
                onChange={(e) => setConsentConfirmed(e.target.checked)}
                required
              />
              {' '}Consent Confirmed *
            </label>
            <small style={{ display: 'block', marginTop: '5px', color: '#666' }}>
              I confirm that I have consent to use this person's images for training.
            </small>
          </div>

          <div className="form-group">
            <label>
              <input
                type="checkbox"
                checked={subjectIsAdult}
                onChange={(e) => setSubjectIsAdult(e.target.checked)}
                required
              />
              {' '}Subject is Adult *
            </label>
            <small style={{ display: 'block', marginTop: '5px', color: '#666' }}>
              I confirm that the subject is an adult (18+ years old).
            </small>
          </div>

          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Creating...' : 'Create Profile'}
          </button>
        </form>
      </div>
    </div>
  )
}
