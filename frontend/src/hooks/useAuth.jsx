import {createContext,useContext,useEffect,useState} from 'react';
import {api} from '@/lib/api';
const AuthContext=createContext(null);
export function AuthProvider({children}){
 const [user,setUser]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState('');
 useEffect(()=>{api('auth/session/').then(d=>setUser(d.user)).catch(e=>setError(e.message)).finally(()=>setLoading(false));const expired=()=>setUser(null);window.addEventListener('session-expired',expired);return()=>window.removeEventListener('session-expired',expired)},[]);
 useEffect(()=>{document.documentElement.style.setProperty("--green",user?.theme?.brand||"#235c49")},[user]);
 return <AuthContext.Provider value={{user,setUser,loading,error,hr:['admin','client_hr'].includes(user?.role),approver:['admin','client_hr','manager'].includes(user?.role),admin:user?.role==='admin'}}>{children}</AuthContext.Provider>
}
export const useAuth=()=>useContext(AuthContext);
