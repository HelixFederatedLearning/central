import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Rounds as API } from '../api/central'
import { Link } from 'react-router-dom'

export default function Rounds() {
  const q = useQuery({ queryKey: ['rounds'], queryFn: API.list })
  return (
    <div className="page">
      <h2>Rounds</h2>
      <table className="table">
        <thead><tr><th>ID</th><th>Status</th><th>Start</th><th>End</th></tr></thead>
        <tbody>
          {q.data?.map((r:any)=>(
            <tr key={r.id}>
              <td><Link to={`/rounds/${r.id}`}>{r.id.slice(0,8)}…</Link></td>
              <td>{r.status}</td>
              <td>{new Date(r.window_start).toLocaleString()}</td>
              <td>{new Date(r.window_end).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
