import {describe,it,expect,vi,beforeEach} from 'vitest';
import {render,screen,waitFor,cleanup} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {MemoryRouter} from 'react-router-dom';
import Payroll,{rowTotal,mergeEmployees} from './index';
import {api} from '@/lib/api';
vi.mock('@/lib/api',()=>({api:vi.fn(),money:v=>Number(v).toFixed(2)}));
vi.mock('@/hooks/useAuth',()=>({useAuth:()=>({hr:true})}));
beforeEach(()=>{cleanup();vi.clearAllMocks();api.mockImplementation(async (path,options)=>{
 if(options?.method==='POST')return {item:{...options.body,id:1,revision:1,status:'draft'}};
 if(path==='companies/')return {items:[{id:1,name:'Example'}]};
 if(path.startsWith('salary-sheets/options'))return {employees:[{id:7,name:'Example Person',emp_no:'E1',status:'active',basic_salary:'70000',epf_eligible:true}]};
 return {items:[],count:0};
})});
describe('salary worksheet',()=>{
 it('links EPF to edited basic salary',()=>{expect(rowTotal({basic_salary:50000,epf_basis:'basic',epf_salary:100,epf_rate:8})).toEqual({epf:4000,total:46000})});
 it('preserves saved rows and adds missing employees once',()=>{const rows=[{employee_id:7,basic_salary:'123'}];const employees=[{id:7},{id:8,basic_salary:'40000'}];expect(mergeEmployees(rows,employees)).toHaveLength(2);expect(mergeEmployees(rows,employees)[0]).toEqual(rows[0])});

 it('previews the template calculation and rounded EPF',()=>{expect(rowTotal({basic_salary:70000,epf_salary:30000,epf_rate:8,leave_deductions:1000,welfare:500,salary_advance:5000})).toEqual({epf:2400,total:61100});expect(rowTotal({epf_salary:12345.67,epf_rate:8}).epf).toBe(987.65)});
 it('automatically loads employees, saves entered amounts and exposes an export',async()=>{const user=userEvent.setup();render(<MemoryRouter><Payroll/></MemoryRouter>);await screen.findByText('No salary sheets yet');await user.click(screen.getByText('New salary sheet'));await user.selectOptions(screen.getByLabelText('Company'),'1');await waitFor(()=>expect(api).toHaveBeenCalledWith('salary-sheets/options/?company=1'));await screen.findByText('Example Person');expect(screen.queryByText('Add row')).toBeNull();expect(screen.queryByText('Remove')).toBeNull();await user.selectOptions(screen.getByLabelText('Example Person: EPF calculation'),'basic');expect(screen.getByLabelText('Example Person: EPF salary').disabled).toBe(true);expect(screen.getByLabelText('Example Person: EPF salary').value).toBe('70000');await user.selectOptions(screen.getByLabelText('Example Person: EPF calculation'),'custom');const input=screen.getByLabelText('Example Person: EPF salary');await user.clear(input);await user.type(input,'30000');await user.click(screen.getByText('Save draft'));await screen.findByText('Draft saved.');expect(api).toHaveBeenCalledWith('salary-sheets/',expect.objectContaining({method:'POST',body:expect.objectContaining({company:1,rows:expect.arrayContaining([expect.objectContaining({employee_id:7,epf_salary:'30000'})])})}));expect(screen.getByText('Download Excel (draft)').getAttribute('href')).toBe('/api/salary-sheets/1/export/');});
});
