import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
import { useRecordingStore } from '@/stores/recording-store';

const EXCEPTION_OPTIONS = [
  { id: 'popup', label: 'Popup dialogs' },
  { id: 'login_expired', label: 'Login expiration' },
  { id: 'slow_loading', label: 'Slow loading' },
];

export function PreRecordForm({ onSubmit }: { onSubmit: () => void }) {
  const { preRecordData, setPreRecordData } = useRecordingStore();

  const canSubmit = preRecordData.purpose.trim().length > 0;

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Pre-recording Setup</h3>
        <p className="text-sm text-muted-foreground">
          Provide context to help AI understand your workflow
        </p>
      </div>

      <div className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="purpose">
            Workflow Purpose <span className="text-destructive">*</span>
          </Label>
          <Input
            id="purpose"
            placeholder="e.g., Download daily sales report from ERP"
            value={preRecordData.purpose}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setPreRecordData({ purpose: e.target.value })}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="apps">Apps / Systems Used</Label>
          <Input
            id="apps"
            placeholder="e.g., Chrome, Excel, SAP (comma-separated)"
            value={preRecordData.apps.join(', ')}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setPreRecordData({
                apps: e.target.value
                  .split(',')
                  .map((s: string) => s.trim())
                  .filter(Boolean),
              })
            }
          />
        </div>

        <div className="space-y-3">
          <Label>Exception Scenarios</Label>
          {EXCEPTION_OPTIONS.map((opt) => (
            <div key={opt.id} className="flex items-center gap-2">
              <Checkbox
                id={opt.id}
                checked={preRecordData.exceptions.includes(opt.id)}
                onCheckedChange={(checked: boolean) => {
                  const next = checked
                    ? [...preRecordData.exceptions, opt.id]
                    : preRecordData.exceptions.filter((e: string) => e !== opt.id);
                  setPreRecordData({ exceptions: next });
                }}
              />
              <Label htmlFor={opt.id} className="font-normal">
                {opt.label}
              </Label>
            </div>
          ))}
        </div>

        <div className="space-y-2">
          <Label htmlFor="exception_notes">Other Exceptions</Label>
          <Textarea
            id="exception_notes"
            placeholder="Describe any other exceptions..."
            value={preRecordData.exception_notes}
            onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
              setPreRecordData({ exception_notes: e.target.value })
            }
            rows={2}
          />
        </div>

        <div className="flex items-center gap-2">
          <Checkbox
            id="sensitive"
            checked={preRecordData.has_sensitive_info}
            onCheckedChange={(checked: boolean) =>
              setPreRecordData({ has_sensitive_info: !!checked })
            }
          />
          <Label htmlFor="sensitive" className="font-normal">
            Contains sensitive info (passwords, personal data)
          </Label>
        </div>
      </div>

      <Button onClick={onSubmit} disabled={!canSubmit} className="w-full">
        Start Recording
      </Button>
    </div>
  );
}
