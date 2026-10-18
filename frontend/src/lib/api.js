let csrf='';
export async function api(path,options={}){
 const form=options.body instanceof FormData;
 const response=await fetch(`/api/${path}`,{credentials:'same-origin',...options,headers:{...(form?{}:{'Content-Type':'application/json'}),'X-CSRFToken':csrf,...options.headers},body:options.body?(form?options.body:JSON.stringify(options.body)):undefined});
 const data=await response.json().catch(()=>({error:'Unexpected server response'}));
 if(!response.ok){const error=new Error(data.error||'Request failed');error.fields=data.fields;error.status=response.status;if(response.status===401)window.dispatchEvent(new Event('session-expired'));throw error;}
 if(data.csrf)csrf=data.csrf;
 return data;
}
export const money=v=>new Intl.NumberFormat('en-LK',{style:'currency',currency:'LKR',maximumFractionDigits:2}).format(Number(v||0));
export const title=v=>String(v||'').replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());
