import { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [urls, setUrls] = useState([])
  const [downloads, setDownloads] = useState({})
  const [sessionId, setSessionId] = useState(null)
  const [isDownloading, setIsDownloading] = useState(false)
  const [report, setReport] = useState(null)
  const [connectionStatus, setConnectionStatus] = useState('disconnected')
  const wsRef = useRef(null)

  useEffect(() => {
    connectWebSocket()
    loadUrls()
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const connectWebSocket = () => {
    const ws = new WebSocket('ws://localhost:3000/ws')
    
    ws.onopen = () => {
      console.log('WebSocket bağlandı')
      setConnectionStatus('connected')
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping')
        }
      }, 30000)
      ws.pingInterval = pingInterval
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      
      if (message.type === 'progress') {
        if (message.session_id && !sessionId) {
          setSessionId(message.session_id)
        }
        
        setDownloads(prev => ({
          ...prev,
          [message.file_id]: {
            ...prev[message.file_id],
            status: message.status,
            progress: message.progress || 0,
            size: message.size || 0,
            totalSize: message.total_size || 0,
            error: message.error || null,
            message: message.message || null
          }
        }))
      } else if (message.type === 'report') {
        if (message.session_id && !sessionId) {
          setSessionId(message.session_id)
        }
        setReport(message.report)
        setIsDownloading(false)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket hatası:', error)
      setConnectionStatus('error')
    }

    ws.onclose = () => {
      console.log('WebSocket bağlantısı kapandı')
      setConnectionStatus('disconnected')
      if (ws.pingInterval) {
        clearInterval(ws.pingInterval)
      }
      setTimeout(() => {
        if (wsRef.current === ws) {
          connectWebSocket()
        }
      }, 5000)
    }

    wsRef.current = ws
  }

  const loadUrls = async () => {
    try {
      const response = await fetch('/api/urls')
      if (response.ok) {
        const data = await response.json()
        setUrls(data.urls)
      }
    } catch (error) {
      console.error('URL listesi yüklenemedi:', error)
    }
  }


  const startDownload = async () => {
    if (urls.length === 0) {
      alert('URL listesi yükleniyor, lütfen bekleyin...')
      return
    }

    setIsDownloading(true)
    setDownloads({})
    setReport(null)

    const initialDownloads = {}
    urls.forEach(url => {
      initialDownloads[url.id] = {
        status: 'pending',
        progress: 0,
        size: 0,
        totalSize: 0
      }
    })
    setDownloads(initialDownloads)
    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const data = await response.json()
      setSessionId(data.session_id)
      console.log('İndirme başlatıldı:', data)
    } catch (error) {
      console.error('İndirme başlatma hatası:', error)
      
      if (error.message.includes('Failed to fetch') || error.message.includes('NetworkError')) {
   
        if (connectionStatus === 'connected') {
          console.log('WebSocket bağlantısı aktif, indirme devam ediyor olabilir')
          const manualSessionId = `session_${Date.now()}`
          setSessionId(manualSessionId)
        } else {
          console.log('WebSocket bağlantısı yok, indirme başlatılamadı')
          setIsDownloading(false)
        }
      } else {
        alert('İndirme başlatılamadı: ' + error.message)
        setIsDownloading(false)
      }
    }
  }

  const downloadReport = async () => {
    if (!sessionId) {
      alert('Henüz bir rapor yok!')
      return
    }

    try {
      console.log('Rapor indiriliyor, session ID:', sessionId)
      const response = await fetch(`/api/report/${sessionId}`)
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      console.log('Response headers:', response.headers)
      console.log('Content-Type:', response.headers.get('content-type'))
      
      const blob = await response.blob()
      console.log('Blob oluşturuldu, boyut:', blob.size)
      
      if (blob.size === 0) {
        throw new Error('Rapor dosyası boş!')
      }
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `download_report_${sessionId}.json`
      a.style.display = 'none'
      document.body.appendChild(a)
      
      console.log('Dosya indirme başlatılıyor...')
      a.click()
      
      setTimeout(() => {
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        console.log('Rapor başarıyla indirildi!')
      }, 100)
      
    } catch (error) {
      console.error('Rapor indirme hatası:', error)
      alert('Rapor indirilemedi: ' + error.message)
    }
  }


  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  const getStatusBadgeClass = (status) => {
    switch (status) {
      case 'downloading':
      case 'pending':
        return 'status-downloading'
      case 'completed':
        return 'status-completed'
      case 'failed':
        return 'status-failed'
      case 'stalled':
        return 'status-stalled'
      default:
        return ''
    }
  }

  const getStatusText = (status) => {
    switch (status) {
      case 'downloading':
        return 'İndiriliyor'
      case 'pending':
        return 'Bekliyor'
      case 'completed':
        return 'Tamamlandı'
      case 'failed':
        return 'Başarısız'
      case 'stalled':
        return 'Duraklatıldı'
      default:
        return status
    }
  }

  return (
    <div className="container">
      <header className="header">
        <h1>🚀 URL Downloader</h1>
        <p>Dosya İndirme ve Durum Kontrol Uygulaması</p>
        <div style={{ marginTop: '16px' }}>
          <span className={`status-indicator ${connectionStatus}`}>
            {connectionStatus === 'connected' ? '🟢 Bağlı' : 
             connectionStatus === 'error' ? '🔴 Hata' : '🟡 Bağlanıyor...'}
          </span>
        </div>
      </header>

      <div className="card">
        <h2>📝 URL Listesi</h2>
        
        <ul className="url-list">
          {urls.map((url) => (
            <li key={url.id} className="url-item">
              <div className="url-item-info">
                <div className="url-item-id">{url.id}</div>
                <div className="url-item-url">{url.url}</div>
              </div>
            </li>
          ))}
        </ul>

        {urls.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">📦</div>
            <div className="empty-state-text">URL listesi yükleniyor...</div>
          </div>
        )}

        <div className="action-buttons">
          <button 
            className="btn btn-primary" 
            onClick={startDownload}
            disabled={isDownloading || urls.length === 0}
          >
            {isDownloading ? (
              <>
                <span className="spinner"></span>
                İndiriliyor...
              </>
            ) : (
              <>⬇️ İndirmeyi Başlat</>
            )}
          </button>
        </div>
      </div>

      {Object.keys(downloads).length > 0 && (
        <div className="card downloads-section">
          <h2>📊 İndirme Durumu</h2>
          
          <div className="alert alert-info">
            ℹ️ Dosyalar 60 saniye sonra duraklamış olup olmadığı kontrol edilecek
          </div>

          {Object.entries(downloads).map(([fileId, download]) => (
            <div key={fileId} className="download-item">
              <div className="download-header">
                <div className="download-title">{fileId}</div>
                <span className={`status-badge ${getStatusBadgeClass(download.status)}`}>
                  {getStatusText(download.status)}
                </span>
              </div>

              {download.status !== 'failed' && (
                <div className="progress-container">
                  <div className="progress-info">
                    <span>{download.progress}%</span>
                    <span>
                      {formatBytes(download.size)}
                      {download.totalSize > 0 && ` / ${formatBytes(download.totalSize)}`}
                    </span>
                  </div>
                  <div className="progress-bar-wrapper">
                    <div 
                      className={`progress-bar ${download.status === 'completed' ? 'completed' : ''}`}
                      style={{ width: `${download.progress}%` }}
                    />
                  </div>
                </div>
              )}

              {download.error && (
                <div style={{ marginTop: '8px', color: 'var(--error-color)', fontSize: '14px' }}>
                  ❌ Hata: {download.error}
                </div>
              )}

              {download.message && (
                <div style={{ marginTop: '8px', color: 'var(--warning-color)', fontSize: '14px' }}>
                  ⚠️ {download.message}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {report && (
        <div className="report-section">
          <div className="report-card">
            <h2>📋 İndirme Raporu</h2>
            
            <div className="report-summary">
              <div className="report-stat">
                <div className="report-stat-label">Başarıyla Tamamlanan</div>
                <div className="report-stat-value">✅ {report.completed_files.length}</div>
              </div>
              <div className="report-stat">
                <div className="report-stat-label">Duraklama Nedeniyle Silinen</div>
                <div className="report-stat-value">🗑️ {report.deleted_files.length}</div>
              </div>
              <div className="report-stat">
                <div className="report-stat-label">İndirilemeyen Dosyalar</div>
                <div className="report-stat-value">⏳ {report.pending_files.length}</div>
              </div>
            </div>

            {report.completed_files.length > 0 && (
              <div className="report-details">
                <h3>✅ Başarıyla Tamamlanan Dosyalar</h3>
                <ul className="report-list">
                  {report.completed_files.map(id => (
                    <li key={id}>• {id}</li>
                  ))}
                </ul>
              </div>
            )}

            {report.deleted_files.length > 0 && (
              <div className="report-details">
                <h3>🗑️ Duraklama Nedeniyle Silinen Dosyalar</h3>
                <ul className="report-list">
                  {report.deleted_files.map(id => (
                    <li key={id}>• {id}</li>
                  ))}
                </ul>
              </div>
            )}

            {report.pending_files.length > 0 && (
              <div className="report-details">
                <h3>⏳ Hiçbir Şekilde İndirilemeyen Dosyalar</h3>
                <ul className="report-list">
                  {report.pending_files.map(id => (
                    <li key={id}>• {id}</li>
                  ))}
                </ul>
              </div>
            )}

            <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap' }}>
              <button className="btn btn-success" onClick={downloadReport}>
                💾 Raporu İndir (.json)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App

