// src/types/schemas.ts
// Zod schemas for form validation.
// Every schema here corresponds to a *Request type in api.ts.

import { z } from "zod";

export const LoginSchema = z.object({
  username: z.string().min(1, "Username is required"),
  password: z.string().min(1, "Password is required"),
});

export type LoginFormValues = z.infer<typeof LoginSchema>;

export const CameraCreateSchema = z.object({
  cam_name: z.string().min(1, "Camera name is required").max(100),
  cam_loc: z.string().min(1, "Location is required").max(300),
  cam_make: z.string().min(1, "Make/model is required").max(100),
  cam_strm1: z
    .string()
    .min(1, "Main stream URL is required")
    .refine((v) => v.startsWith("rtsp://") || v.startsWith("rtmp://"), {
      message: "Stream URL must start with rtsp:// or rtmp://",
    }),
  cam_strm2: z.string().optional(),
  cam_strm3: z.string().optional(),
  cam_usrname: z.string().min(1, "Username is required"),
  cam_pass: z.string().min(1, "Password is required"),
  cam_onvif: z.number().int().positive().optional(),
  strm_type_id: z.number().int().positive("Stream type is required"),
  com_id: z.number().int().positive("Customer is required"),
  device_id: z.number().int().positive("Device is required"),
  is_active: z.boolean().default(true),
  motion_active: z.boolean().default(false),
});

export type CameraCreateFormValues = z.infer<typeof CameraCreateSchema>;

export const CameraUpdateSchema = CameraCreateSchema.partial().omit({
  com_id: true,
  device_id: true,
});

export type CameraUpdateFormValues = z.infer<typeof CameraUpdateSchema>;

export const CustomerCreateSchema = z.object({
  com_name: z.string().min(1, "Company name is required").max(255),
  com_adr: z.string().min(1, "Address is required"),
  gstn: z
    .string()
    .regex(/^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/, "Invalid GST number")
    .optional()
    .or(z.literal("")),
  cir_id: z.number().int().positive("Circle is required"),
  ba_id: z.number().int().positive("Business area is required"),
  plan_id: z.number().int().positive("Plan is required"),
});

export type CustomerCreateFormValues = z.infer<typeof CustomerCreateSchema>;

export const UserCreateSchema = z.object({
  username: z.string().min(3, "Username must be at least 3 characters").max(150),
  password: z
    .string()
    .min(8, "Password must be at least 8 characters")
    .regex(/[A-Z]/, "Must contain uppercase letter")
    .regex(/[0-9]/, "Must contain a number"),
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  email: z.string().email("Invalid email address"),
  role: z.enum(["sysadmin", "circle_admin", "ba_admin", "cust_admin", "viewer"]),
  com_id: z.number().int().positive().optional(),
  cir_id: z.number().int().positive().optional(),
  ba_id: z.number().int().positive().optional(),
});

export type UserCreateFormValues = z.infer<typeof UserCreateSchema>;

export const UserUpdateSchema = z.object({
  email: z.string().email("Invalid email address").optional(),
  first_name: z.string().min(1).optional(),
  last_name: z.string().min(1).optional(),
  role: z
    .enum(["sysadmin", "circle_admin", "ba_admin", "cust_admin", "viewer"])
    .optional(),
  com_id: z.number().int().positive().optional().nullable(),
  cir_id: z.number().int().positive().optional().nullable(),
  ba_id: z.number().int().positive().optional().nullable(),
  is_active: z.boolean().optional(),
});

export type UserUpdateFormValues = z.infer<typeof UserUpdateSchema>;

export const ChangePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z
      .string()
      .min(8, "New password must be at least 8 characters")
      .regex(/[A-Z]/, "Must contain uppercase letter")
      .regex(/[0-9]/, "Must contain a number"),
    confirm_password: z.string().min(1, "Please confirm your new password"),
  })
  .refine((data) => data.new_password === data.confirm_password, {
    message: "Passwords do not match",
    path: ["confirm_password"],
  });

export type ChangePasswordFormValues = z.infer<typeof ChangePasswordSchema>;

export const RecordingFilterSchema = z.object({
  cam_id: z.string().optional(),
  start: z.string().min(1, "Start date is required"),
  end: z.string().min(1, "End date is required"),
  page: z.number().int().positive().default(1),
  page_size: z.number().int().positive().default(25),
});

export type RecordingFilterValues = z.infer<typeof RecordingFilterSchema>;
