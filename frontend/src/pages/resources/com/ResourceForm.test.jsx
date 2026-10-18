import {describe,it,expect,vi,afterEach} from 'vitest';
import {render,screen,waitFor,cleanup} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ResourceForm from './ResourceForm';
import {api} from '@/lib/api';
vi.mock('@/lib/api',()=>({api:vi.fn()}));
afterEach(()=>{cleanup();vi.clearAllMocks()});
describe('Resource forms',()=>{
 it('loads field schema and submits values to the real resource path',async()=>{api.mockResolvedValueOnce({fields:[{name:'full_name',label:'Full name',type:'text',required:true,initial:''}]}).mockResolvedValueOnce({item:{id:4}});const saved=vi.fn();render(<ResourceForm name="employees" item={null} onSaved={saved} onClose={()=>{}}/>);await userEvent.type(await screen.findByLabelText(/Full name/),'Sample Person');await userEvent.click(screen.getByRole('button',{name:'Save changes'}));await waitFor(()=>expect(saved).toHaveBeenCalledOnce());expect(api).toHaveBeenLastCalledWith('employees/',{method:'POST',body:{full_name:'Sample Person'}})});
 it('keeps failed forms open and displays backend validation',async()=>{api.mockResolvedValueOnce({fields:[{name:'reason',label:'Reason',type:'text',required:true,initial:'Test'}]}).mockRejectedValueOnce(Object.assign(new Error('Not enough leave'),{fields:{reason:[{message:'Check your balance'}]}}));const saved=vi.fn();render(<ResourceForm name="leave" item={null} onSaved={saved} onClose={()=>{}}/>);await screen.findByLabelText(/Reason/);await userEvent.click(screen.getByRole('button',{name:'Save changes'}));expect((await screen.findByRole('alert')).textContent).toContain('Not enough leave');expect(saved).not.toHaveBeenCalled()});
});
