import React, { useEffect, useState } from 'react'
import { Rounds } from '../api/central'

export default function EventTicker() {
  const [lines, setLines] = useState<string[]>([])
  useEffect(() => {
    const es = new EventSource(Rounds.eventsURL())
    es.onmessage = (e) => {
      try {
        const obj = JSON.parse((e as MessageEvent).data)
        const t = (() => {
          switch (obj.type) {
            case 'delta_received': return `Δ ${obj.kind} from ${obj.client_id} (n=${obj.n})`
            case 'model_published': return `Model published ${obj.version}`
            case 'model_promoted': return `Model promoted ${obj.version}`
            case 'round_status': return `Round ${obj.round_id} → ${obj.status}`
            default: return JSON.stringify(obj)
          }
        })()
        setLines(prev => [t, ...prev].slice(0, 50))
      } catch {}
    }
    return () => es.close()
  }, [])
  return (
    <div className="ticker">
      <div className="ticker-title">Live</div>
      <ul>{lines.map((l,i)=><li key={i}>{l}</li>)}</ul>
    </div>
  )
}
