import {Button as BaseButton} from '@base-ui/react/button';
export default function Button({variant='primary',className='',children,...props}){return <BaseButton className={`btn ${variant} ${className}`} {...props}>{children}</BaseButton>}
