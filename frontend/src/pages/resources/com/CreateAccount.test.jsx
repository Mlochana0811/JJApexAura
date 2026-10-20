import {it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CreateAccount from './CreateAccount';
import {api} from '@/lib/api';
vi.mock('@/lib/api',()=>({api:vi.fn(async()=>({ok:true}))}));
it('creates an HR account and clears the temporary password',async()=>{
 const user=userEvent.setup();render(<CreateAccount employee={{id:5,email:'user@example.invalid'}} onUpdated={()=>{}}/>);
 await user.type(screen.getByLabelText('Username'),'newlogin');await user.type(screen.getByLabelText('Temporary password'),'Temporary!Unique482');await user.selectOptions(screen.getByLabelText('Login role'),'client_hr');await user.click(screen.getByRole('button',{name:'Create login account'}));
 await screen.findByRole('status');expect(api).toHaveBeenCalledWith('employees/5/create-account/',expect.objectContaining({body:expect.objectContaining({role:'client_hr',username:'newlogin'})}));expect(screen.getByLabelText('Temporary password').value).toBe('');
});
