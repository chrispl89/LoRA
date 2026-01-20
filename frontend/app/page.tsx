'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Person } from '@/types'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function Home() {
  const [persons, setPersons] = useState<Person[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchPersons()
  }, [])

  const fetchPersons = async () => {
    try {
      const response = await fetch(`${API_URL}/v1/persons`)
      if (!response.ok) throw new Error('Failed to fetch persons')
      const data = await response.json()
      setPersons(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading...</div>
  if (error) return <div className="error">Error: {error}</div>

  return (
    <div className="container">
      <h1>LoRA Person MVP</h1>
      <div style={{ marginBottom: '20px' }}>
        <Link href="/persons/create" className="btn btn-primary">
          Create Person Profile
        </Link>
      </div>

      <div className="grid grid-2">
        {persons.map((person) => (
          <div key={person.id} className="card">
            <h2>{person.name}</h2>
            <p>
              Consent: {person.consent_confirmed ? '✓' : '✗'} | 
              Adult: {person.subject_is_adult ? '✓' : '✗'}
            </p>
            <div style={{ marginTop: '15px' }}>
              <Link href={`/persons/${person.id}`} className="btn btn-primary" style={{ marginRight: '10px' }}>
                View Profile
              </Link>
            </div>
          </div>
        ))}
      </div>

      {persons.length === 0 && (
        <div className="card">
          <p>No persons found. Create your first person profile to get started.</p>
        </div>
      )}
    </div>
  )
}
