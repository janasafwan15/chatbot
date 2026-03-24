import { useState, useEffect } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Clock, Trash2 } from 'lucide-react';
import { Button } from './ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { toast } from 'sonner';

export interface UploadedFile {
  id: string;
  name: string;
  content: string;
  type: string;
  size: number;
  uploadedBy: string;
  uploadedAt: Date;
  status: 'pending' | 'approved' | 'rejected';
  rejectionReason?: string;
}

export function FileManagement() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    // تحميل الملفات من localStorage
    const savedFiles = localStorage.getItem('uploadedFiles');
    if (savedFiles) {
      const parsedFiles = JSON.parse(savedFiles);
      // تحويل التواريخ من string إلى Date
      const filesWithDates = parsedFiles.map((file: any) => ({
        ...file,
        uploadedAt: new Date(file.uploadedAt)
      }));
      setFiles(filesWithDates);
    }
  }, []);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles || selectedFiles.length === 0) return;

    setUploading(true);

    try {
      const newFiles: UploadedFile[] = [];

      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        
        // التحقق من نوع الملف
        const allowedTypes = [
          'text/plain',
          'application/pdf',
          'application/msword',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        ];
        
        if (!allowedTypes.includes(file.type) && !file.name.endsWith('.txt')) {
          toast.error(`نوع الملف ${file.name} غير مدعوم`);
          continue;
        }

        // التحقق من حجم الملف (أقل من 5 ميجابايت)
        if (file.size > 5 * 1024 * 1024) {
          toast.error(`الملف ${file.name} كبير جداً (الحد الأقصى 5 ميجابايت)`);
          continue;
        }

        // قراءة محتوى الملف
        const content = await readFileContent(file);

        const newFile: UploadedFile = {
          id: `file_${Date.now()}_${i}`,
          name: file.name,
          content: content,
          type: file.type || 'text/plain',
          size: file.size,
          uploadedBy: 'موظف', // في التطبيق الحقيقي سيكون اسم المستخدم
          uploadedAt: new Date(),
          status: 'pending'
        };

        newFiles.push(newFile);
      }

      // حفظ الملفات الجديدة
      const updatedFiles = [...files, ...newFiles];
      setFiles(updatedFiles);
      localStorage.setItem('uploadedFiles', JSON.stringify(updatedFiles));

      toast.success(`تم رفع ${newFiles.length} ملف بنجاح. في انتظار موافقة الإدارة`);
    } catch (error) {
      console.error('خطأ في رفع الملف:', error);
      toast.error('حدث خطأ أثناء رفع الملف');
    } finally {
      setUploading(false);
      // إعادة تعيين input
      event.target.value = '';
    }
  };

  const readFileContent = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        const content = e.target?.result as string;
        resolve(content);
      };
      
      reader.onerror = () => {
        reject(new Error('فشل قراءة الملف'));
      };

      // قراءة الملف كنص
      if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
        reader.readAsText(file);
      } else {
        // للملفات الأخرى، نحفظ فقط البيانات الوصفية
        resolve('[محتوى ثنائي - سيتم معالجته عند الموافقة]');
      }
    });
  };

  const handleDelete = (fileId: string) => {
    const updatedFiles = files.filter(f => f.id !== fileId);
    setFiles(updatedFiles);
    localStorage.setItem('uploadedFiles', JSON.stringify(updatedFiles));
    toast.success('تم حذف الملف');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'approved':
        return (
          <Badge className="bg-green-500 text-white">
            <CheckCircle className="w-3 h-3 ml-1" />
            موافق عليه
          </Badge>
        );
      case 'rejected':
        return (
          <Badge className="bg-red-500 text-white">
            <XCircle className="w-3 h-3 ml-1" />
            مرفوض
          </Badge>
        );
      default:
        return (
          <Badge className="bg-yellow-500 text-white">
            <Clock className="w-3 h-3 ml-1" />
            قيد المراجعة
          </Badge>
        );
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' بايت';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' كيلوبايت';
    return (bytes / (1024 * 1024)).toFixed(1) + ' ميجابايت';
  };

  const myFiles = files.filter(f => f.uploadedBy === 'موظف');

  return (
    <div className="space-y-6" dir="rtl">
      <Card>
        <CardHeader>
          <CardTitle>رفع ملفات البيانات</CardTitle>
          <CardDescription>
            قم برفع ملفات تحتوي على معلومات ومعرفة لإضافتها إلى نظام الذكاء الاصطناعي. 
            الملفات المرفوعة تحتاج موافقة الإدارة قبل إضافتها للنظام.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col gap-4">
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition-colors">
              <input
                type="file"
                id="file-upload"
                multiple
                accept=".txt,.pdf,.doc,.docx"
                onChange={handleFileUpload}
                className="hidden"
                disabled={uploading}
              />
              <label
                htmlFor="file-upload"
                className="cursor-pointer flex flex-col items-center gap-3"
              >
                <Upload className="w-12 h-12 text-gray-400" />
                <div>
                  <p className="text-lg font-medium text-gray-700">
                    اضغط لرفع الملفات
                  </p>
                  <p className="text-sm text-gray-500 mt-1">
                    أنواع الملفات المدعومة: TXT, PDF, DOC, DOCX (حتى 5 ميجابايت)
                  </p>
                </div>
                {uploading && (
                  <p className="text-blue-600 font-medium">جاري الرفع...</p>
                )}
              </label>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-medium text-blue-900 mb-2">إرشادات رفع الملفات:</h4>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• تأكد من أن الملفات تحتوي على معلومات دقيقة وموثوقة</li>
                <li>• استخدم ملفات نصية بسيطة للحصول على أفضل نتائج</li>
                <li>• الملفات المرفوعة ستتم مراجعتها قبل إضافتها للنظام</li>
                <li>• يمكنك رفع عدة ملفات في نفس الوقت</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>الملفات المرفوعة</CardTitle>
          <CardDescription>
            عرض جميع الملفات التي قمت برفعها وحالتها
          </CardDescription>
        </CardHeader>
        <CardContent>
          {myFiles.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="w-12 h-12 mx-auto mb-3 text-gray-400" />
              <p>لم تقم برفع أي ملفات بعد</p>
            </div>
          ) : (
            <div className="space-y-3">
              {myFiles.map((file) => (
                <div
                  key={file.id}
                  className="border rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      <FileText className="w-5 h-5 text-blue-600 mt-1" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <h4 className="font-medium text-gray-900">{file.name}</h4>
                          {getStatusBadge(file.status)}
                        </div>
                        <div className="text-sm text-gray-500 space-y-1">
                          <p>الحجم: {formatFileSize(file.size)}</p>
                          <p>تاريخ الرفع: {file.uploadedAt.toLocaleDateString('ar-EG', {
                            year: 'numeric',
                            month: 'long',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit'
                          })}</p>
                          {file.status === 'rejected' && file.rejectionReason && (
                            <p className="text-red-600 mt-2">
                              <span className="font-medium">سبب الرفض:</span> {file.rejectionReason}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                    {file.status === 'pending' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(file.id)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
