import type { Report } from '../lib/reconciliation'

interface Props {
  report: Report
  onRestart: () => void
}

export default function ReconciliationReport({ report, onRestart }: Props) {
  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <h1>Rapport de rapprochement</h1>
      <p>Transactions : {report.total_transactions}</p>
      <p>Rapprochées : {report.total_rapprochees}</p>
      <p>Non rapprochées : {report.total_non_rapprochees}</p>
      <p>Écarts : {report.total_ecarts}</p>

      <h3>Matches</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Facture</th>
            <th>Transaction</th>
            <th>Statut</th>
            <th>Écart</th>
          </tr>
        </thead>
        <tbody>
          {report.matches.map(m => (
            <tr key={`${m.facture_id}-${m.transaction_id}`}>
              <td>{m.facture_id}</td>
              <td>{m.transaction_id}</td>
              <td>{m.statut}</td>
              <td>{m.ecart_montant}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Non rapprochées</h3>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>Transaction</th>
            <th>Montant</th>
            <th>Date</th>
            <th>Libellé</th>
          </tr>
        </thead>
        <tbody>
          {report.unmatched.map(t => (
            <tr key={t.id}>
              <td>{t.id}</td>
              <td>{t.montant}</td>
              <td>{t.date}</td>
              <td>{t.libelle}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <button onClick={onRestart} style={{ marginTop: 16 }}>Nouveau rapprochement</button>
    </div>
  )
}
