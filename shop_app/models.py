from django.db import models
from django.utils.text import slugify
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django_rest_passwordreset.signals import reset_password_token_created
from django.dispatch import receiver
from django.utils.html import strip_tags 
from django.template.loader import render_to_string
from django.urls import reverse 

BASE_URL=settings.REACT_BASE_URL 

# Create your models here.
class Product(models.Model):
    CATEGORY = [
        ('Electronics', 'Electronics'),
        ('Groceries', 'Groceries'),
        ('Clothing', 'Clothing'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(null=True, blank=True)
    image = models.ImageField(upload_to='img')
    description = models.TextField(blank=True,null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=15, choices=CATEGORY,blank=True,null=True)
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            unique_slug=self.slug
            counter=1
            if Product.objects.filter(slug=unique_slug).exists():
                unique_slug=f'{self.slug}{counter}'
                counter+=1
            self.slug=unique_slug  
              
        super().save(*args, **kwargs)

class Cart(models.Model):
    cart_code=models.CharField(max_length=11,unique=True)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,blank=True,null=True,related_name="carts")
    paid=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True,blank=True,null=True)
    modified_at=models.DateTimeField(auto_now=True,blank=True,null=True)   

    def __str__(self):
        return self.cart_code  
           
class CartItem(models.Model):
    cart=models.ForeignKey(Cart,related_name='items',on_delete=models.CASCADE)    
    product=models.ForeignKey(Product,on_delete=models.CASCADE)  
    quantity=models.IntegerField(default=1)  

    def __str__(self):
        return f'{self.quantity} x {self.product.name} in cart {self.cart_id}'
        
class Transaction(models.Model):
    ref=models.CharField(max_length=255,unique=True)
    cart=models.ForeignKey(Cart,on_delete=models.CASCADE,related_name="transactions")
    amount=models.DecimalField(max_digits=10,decimal_places=2)
    currency=models.CharField(max_length=10,default="USD")
    status=models.CharField(max_length=20,default="pending")
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE,blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)   
    modified_at=models.DateTimeField(auto_now=True)   

    def __str__(self):
        return f"Transaction {self.ref} - {self.status}" 

@receiver(reset_password_token_created)
def password_reset_token_created(reset_password_token, *args, **kwargs):
    sitelink = BASE_URL
    token = "{}".format(reset_password_token.key)
    full_link = str(sitelink)+str("password-reset/")+str(token)

    print(token)
    print(full_link)

    context = {
        'full_link': full_link,
        'email_adress': reset_password_token.user.email
    }

    html_message = render_to_string("backend/email.html", context=context)
    plain_message = strip_tags(html_message)

    msg = EmailMultiAlternatives(
        subject = "Request for resetting password for {title}".format(title=reset_password_token.user.email), 
        body=plain_message,
        from_email = "mujames008@gmail.com", 
        to=[reset_password_token.user.email]
    )

    msg.attach_alternative(html_message, "text/html")
    msg.send()        