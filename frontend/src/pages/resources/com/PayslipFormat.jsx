export default function PayslipFormat({value,onChange}){
 return <label className="field"><span>Payslip format</span><select aria-label="Payslip format" value={value} onChange={e=>onChange(e.target.value)}><option value="">Company default</option><option value="classic">Classic gold (example layout)</option><option value="navy">Navy & teal</option></select><small>Changes the PDF appearance only. Approved salary figures stay the same.</small></label>
}
