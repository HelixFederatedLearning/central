import React from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Rounds as API } from '../api/central'

export default function RoundDetail() {
  const { id } = useParams()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['round', id], queryFn: ()=>API.get(id!) })
  const agg = useMutation({ mutationFn: ()=>API.aggregate(id!), onSuccess: ()=>qc.invalidateQueries({queryKey:['round', id]}) })
  const r = q.data?.round, deltas = q.data?.deltas || []
  return (
    <div className="page">
      <h2>Round {id?.slice(0,8)}…</h2>
      {r && <div className="card">
        <div>Status: <b>{r.status}</b></div>
        <div>Window: {new Date(r.window_start).toLocaleString()} → {new Date(r.window_end).toLocaleString()}</div>
        <button className="btn" onClick={()=>agg.mutate()} disabled={agg.isPending || r.status==='published'}>
          {agg.isPending ? 'Aggregating…' : 'Aggregate now'}
        </button>
      </div>}
      <h3>Deltas</h3>
      <table className="table">
        <thead><tr><th>Client</th><th>Kind</th><th>n</th><th>Received</th></tr></thead>
        <tbody>
          {deltas.map((d:any)=>(
            <tr key={d.id}>
              <td>{d.client_id}</td><td>{d.kind}</td><td>{d.num_examples}</td>
              <td>{new Date(d.received_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
