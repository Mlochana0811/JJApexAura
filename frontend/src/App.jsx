import {BrowserRouter} from 'react-router-dom';
import {AuthProvider} from '@/hooks/useAuth';
import AppRoutes from '@/routing/AppRoutes';
export default function App(){return <BrowserRouter basename="/app"><AuthProvider><AppRoutes/></AuthProvider></BrowserRouter>}
