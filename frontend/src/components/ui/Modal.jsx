import {Dialog} from '@base-ui/react/dialog';
import {X} from 'lucide-react';
export default function Modal({open,onClose,title,children}){return <Dialog.Root open={open} onOpenChange={v=>!v&&onClose()}><Dialog.Portal><Dialog.Backdrop className="modal-backdrop"/><Dialog.Popup className="modal"><header><Dialog.Title>{title}</Dialog.Title><Dialog.Close className="icon-button" aria-label="Close"><X size={20}/></Dialog.Close></header><div className="modal-body">{children}</div></Dialog.Popup></Dialog.Portal></Dialog.Root>}
