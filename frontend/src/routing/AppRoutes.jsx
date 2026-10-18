import {Routes,Route,Navigate,Outlet} from 'react-router-dom';
import {useAuth} from '@/hooks/useAuth';
import AppLayout from '@/layouts/AppLayout';
import {lazy,Suspense} from 'react';
const Dashboard=lazy(()=>import('@/pages/dashboard'));
const ResourcePage=lazy(()=>import('@/pages/resources'));
const AuthPage=lazy(()=>import('@/pages/auth'));
function Guard(){const {user}=useAuth();if(!user)return <Navigate to="/login" replace/>;if(user.must_change_password)return <Navigate to="/password" replace/>;return <Outlet/>}
export default function AppRoutes(){const {loading,error,user}=useAuth();if(loading)return <div className="loading">Opening Jay’s HR…</div>;if(error)return <div className="loading">Cannot reach the HR server: {error}. Start the backend and reload.</div>;return <Suspense fallback={<div className="loading">Loading workspace…</div>}><Routes><Route path="/login" element={user?<Navigate to={user.must_change_password?'/password':'/'} replace/>:<AuthPage/>}/><Route path="/password" element={user?<AuthPage mode="password"/>:<Navigate to="/login"/>}/><Route path="/forgot" element={<AuthPage mode="forgot"/>}/><Route path="/reset/:uid/:token" element={<AuthPage mode="reset"/>}/><Route path="/invite/:token" element={<AuthPage mode="invite"/>}/><Route element={<Guard/>}><Route element={<AppLayout/>}><Route index element={<Dashboard/>}/><Route path="/:name" element={<ResourcePage/>}/></Route></Route><Route path="*" element={<Navigate to="/"/>}/></Routes></Suspense>}
