from django import forms

from .models import MAX_TAG_LENGTH, MAX_TAGS_PER_NOTE, Note


def parse_tags(raw):
    """'Work, ideas,WORK' -> ['work', 'ideas']. Lowercased, de-duplicated, order kept."""
    seen = []
    for part in (raw or "").replace("#", "").split(","):
        name = " ".join(part.split()).lower()
        if name and name not in seen:
            seen.append(name)
    if len(seen) > MAX_TAGS_PER_NOTE:
        raise forms.ValidationError(f"Use at most {MAX_TAGS_PER_NOTE} tags per note.")
    if any(len(n) > MAX_TAG_LENGTH for n in seen):
        raise forms.ValidationError(f"Tags can be up to {MAX_TAG_LENGTH} characters.")
    return seen


class NoteForm(forms.ModelForm):
    body = forms.CharField(required=False, max_length=100_000, widget=forms.Textarea(
        attrs={"placeholder": "Start writing…", "aria-label": "Note body", "rows": 14}))
    tags = forms.CharField(required=False, max_length=500, widget=forms.TextInput(
        attrs={"placeholder": "Add tags, separated by commas", "aria-label": "Tags", "autocomplete": "off"}))

    class Meta:
        model = Note
        fields = ["title", "body"]
        widgets = {"title": forms.TextInput(attrs={
            "placeholder": "Untitled note", "aria-label": "Note title", "autocomplete": "off"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["tags"].initial = self.instance.tag_string()

    def clean_tags(self):
        return parse_tags(self.cleaned_data.get("tags", ""))

    def save(self, commit=True):
        note = super().save(commit=commit)
        if commit:
            note.set_tags(self.cleaned_data["tags"])
        return note
