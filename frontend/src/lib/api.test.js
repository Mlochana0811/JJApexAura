import {describe,it,expect,vi,afterEach} from 'vitest';
import {api,money,title} from './api';
afterEach(()=>vi.unstubAllGlobals());
describe('API client',()=>{
 it('uses CSRF tokens returned by the server',async()=>{const fetch=vi.fn().mockResolvedValueOnce({ok:true,json:async()=>({csrf:'test-csrf'})}).mockResolvedValueOnce({ok:true,json:async()=>({ok:true})});vi.stubGlobal('fetch',fetch);await api('auth/session/');await api('leave/',{method:'POST',body:{reason:'Family'}});expect(fetch.mock.calls[1][1].headers['X-CSRFToken']).toBe('test-csrf');expect(fetch.mock.calls[1][1].body).toBe('{"reason":"Family"}');});
 it('surfaces validation errors rather than treating failure as success',async()=>{vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:400,json:async()=>({error:'Invalid date',fields:{date:[{message:'Required'}]}})}));await expect(api('leave/')).rejects.toMatchObject({message:'Invalid date',status:400,fields:{date:[{message:'Required'}]}})});
 it('formats payroll currency and labels',()=>{expect(money('12500.5')).toContain('12,500.50');expect(title('client_hr')).toBe('Client Hr')});
});
