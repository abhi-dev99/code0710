import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import LiveFireTerminal from '../LiveFireTerminal.jsx'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LiveFireTerminal />
  </StrictMode>,
)
