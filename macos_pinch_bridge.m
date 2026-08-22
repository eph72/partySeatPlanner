#import <Cocoa/Cocoa.h>
#import <objc/runtime.h>

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

typedef struct {
    int writeFileDescriptor;
} PSPPinchContext;

static char PSPContextAssociationKey;

static PSPPinchContext *PSPContextForView(NSView *view) {
    NSValue *value = objc_getAssociatedObject(view, &PSPContextAssociationKey);
    return value ? [value pointerValue] : NULL;
}

static int PSPSendPinch(PSPPinchContext *context, double amount) {
    if (!context || amount == 0.0) {
        return 0;
    }
    ssize_t bytesWritten = write(context->writeFileDescriptor, &amount, sizeof(amount));
    return bytesWritten == (ssize_t)sizeof(amount);
}

static void PSPMagnifyWithEvent(id nativeSelf, SEL selector, NSEvent *event) {
    (void)selector;
    PSPSendPinch(PSPContextForView((NSView *)nativeSelf), [event magnification]);
}

int PSPInstallPinchHandler(void *rawView, int writeFileDescriptor) {
    if (!rawView || writeFileDescriptor < 0) {
        return 0;
    }

    NSView *view = (__bridge NSView *)rawView;
    Class originalClass = object_getClass(view);
    if (!originalClass) {
        return 0;
    }

    char className[96];
    snprintf(
        className,
        sizeof(className),
        "PartySeatPlannerPinchView_%llx",
        (unsigned long long)(uintptr_t)view
    );
    Class pinchClass = objc_allocateClassPair(originalClass, className, 0);
    if (!pinchClass) {
        return 0;
    }
    BOOL added = class_addMethod(
        pinchClass,
        @selector(magnifyWithEvent:),
        (IMP)PSPMagnifyWithEvent,
        "v@:@"
    );
    if (!added) {
        objc_disposeClassPair(pinchClass);
        return 0;
    }

    PSPPinchContext *context = calloc(1, sizeof(PSPPinchContext));
    if (!context) {
        objc_disposeClassPair(pinchClass);
        return 0;
    }
    context->writeFileDescriptor = writeFileDescriptor;

    objc_registerClassPair(pinchClass);
    objc_setAssociatedObject(
        view,
        &PSPContextAssociationKey,
        [NSValue valueWithPointer:context],
        OBJC_ASSOCIATION_RETAIN_NONATOMIC
    );
    object_setClass(view, pinchClass);
    return 1;
}

int PSPTestPinch(void *rawView, double amount) {
    if (!rawView) {
        return 0;
    }
    NSView *view = (__bridge NSView *)rawView;
    return PSPSendPinch(PSPContextForView(view), amount);
}
