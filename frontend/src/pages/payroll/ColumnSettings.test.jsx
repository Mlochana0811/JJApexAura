import {it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ColumnSettings from './ColumnSettings';
import {defaultConfig} from './TemplateSheet';
import {api} from '@/lib/api';
vi.mock('@/lib/api',()=>({api:vi.fn(),money:String}));
it('saves visibility in payroll settings while preserving salary amounts',async()=>{
 const sheet={id:4,company:1,company_name:'Example',year:2026,month:10,status:'draft',revision:3,template_config:defaultConfig,rows:[{employee_id:7,basic_salary:'50000'}]};
 api.mockImplementation(async(path,opts)=>opts?{item:opts.body}:path==='salary-sheets/4/'?{item:sheet}:{items:[sheet],count:1});
 const user=userEvent.setup();render(<ColumnSettings/>);await screen.findByText('Example — 2026-10');await user.selectOptions(screen.getByLabelText('Salary sheet'),'4');
 await screen.findByLabelText('Show Basic salary');await user.selectOptions(screen.getByLabelText('Show Basic salary'),'false');await user.click(screen.getByText('Save column settings'));await screen.findByText('Column settings saved.');
 const saved=api.mock.calls.find(([,o])=>o?.method==='POST')[1].body;
 expect(saved.template_config.column_visibility.basic_salary).toBe(false);expect(saved.rows[0].basic_salary).toBe('50000');expect(saved.revision).toBe(3);
});
