import {it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import PayslipFormat from './PayslipFormat';
it('lets the user select the example format',async()=>{const onChange=vi.fn();render(<PayslipFormat value="" onChange={onChange}/>);await userEvent.selectOptions(screen.getByLabelText('Payslip format'),'classic');expect(onChange).toHaveBeenCalledWith('classic');expect(screen.getByRole('option',{name:'Navy & teal'})).toBeTruthy()});
