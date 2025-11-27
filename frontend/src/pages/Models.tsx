import React from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Models as API } from '../api/central'

export default function Models() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['models'], queryFn: API.list })
  const promote = useMutation({ mutationFn: (id:string)=>API.promote(id), onSuccess: ()=>qc.invalidateQueries({queryKey:['models']}) })
  return (
    <div className="page">
      <h2>Model Registry</h2>
      <table className="table">
        <thead><tr><th>Version</th><th>Checksum</th><th>Created</th><th></th></tr></thead>
        <tbody>
          {list.data?.map((m:any)=>(
            <tr key={m.id}>
              <td>{m.version}</td>
              <td className="mono">{m.checksum.slice(0,18)}…</td>
              <td>{new Date(m.created_at).toLocaleString()}</td>
              <td><button className="btn" onClick={()=>promote.mutate(m.id)}>Promote</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
