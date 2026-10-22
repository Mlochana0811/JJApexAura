import {it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ColumnSettings from './ColumnSettings';
import {api} from '@/lib/api';
vi.mock('@/lib/api',()=>({api:vi.fn()}));
it('shows company column checkboxes without requiring a salary sheet',async()=>{
 api.mockImplementation(async(path,opts)=>path==='companies/'?{items:[{id:1,name:'Example'}]}:{columns:[{key:'basic_salary',label:'Basic salary'}],visibility:opts?.body.visibility||{},revision:0});
 const user=userEvent.setup();render(<ColumnSettings/>);await screen.findByText('Example');await user.selectOptions(screen.getByLabelText('Company for salary columns'),'1');
 await screen.findByLabelText('Show Basic salary');expect(screen.getByLabelText('Show Basic salary').checked).toBe(true);await user.click(screen.getByLabelText('Show Basic salary'));await user.click(screen.getByText('Save column settings'));await screen.findByRole('status');
 const saved=api.mock.calls.find(([,o])=>o?.method==='POST')[1].body;expect(saved.visibility.basic_salary).toBe(false);expect(saved.company).toBe(1);expect(screen.queryByText('Add column')).toBeNull();
});
