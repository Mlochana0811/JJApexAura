import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './styles/index.css';
if(location.pathname==='/')location.replace('/app/');
createRoot(document.getElementById('root')).render(<StrictMode><App/></StrictMode>);
